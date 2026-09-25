# mihuSound.py
# Biblioteca de som para MIHU-S3 / ESP32-S3 com MAX98357A
# Recursos:
# - Tons e notas musicais simples
# - Melodias com nomes de notas
# - Reprodução de arquivos WAV do aluno
# - Controle de volume 0..100
# - Inicialização I2S sob demanda para economizar memória

from machine import Pin, I2S
import math
import time
import gc


class MihuSound:
    # -------------------------------------------------
    # IDs compatíveis com versões anteriores
    # -------------------------------------------------
    SOUND_PRESS       = 1
    SOUND_ERROR       = 2
    SOUND_POWER_LOW   = 3
    SOUND_OK          = 4
    SOUND_RUN_START   = 5
    SOUND_RUN_STOP    = 6
    SOUND_POWER_ON    = 7
    SOUND_POWER_OFF   = 8
    SOUND_RB_MOVE     = 9
    SOUND_RB_SPEAKER  = 10
    SOUND_RB_FIRE     = 11
    SOUND_RB_ESCAPE   = 12
    SOUND_RB_DOG      = 13
    SOUND_RB_CAT      = 14
    SOUND_RB_BIRD     = 15
    SOUND_RB_VICTORY  = 16
    SOUND_RB_FAIL     = 17
    SOUND_MUSIC1      = 18

    # -------------------------------------------------
    # Tabela de notas
    # -------------------------------------------------
    _NOTE_BASE = {
        "C": 0,  "DO": 0,
        "D": 2,  "RE": 2,
        "E": 4,  "MI": 4,
        "F": 5,  "FA": 5,
        "G": 7,  "SOL": 7,
        "A": 9,  "LA": 9,
        "B": 11, "SI": 11,
    }

    _REST_NAMES = ("P", "PAUSA", "SILENCIO", "SILÊNCIO", "REST", "-", "0", "")

    def __init__(
        self,
        bclk=21,
        lrck=38,
        din=0,
        i2s_id=1,
        sample_rate=16000,
        block_size=128,
        ibuf=2048,
        volume=70,
        max_amplitude=4000,
        fade_ms=4,
        auto_init=False
    ):
        self.bclk = bclk
        self.lrck = lrck
        self.din = din
        self.i2s_id = i2s_id

        self.SAMPLE_RATE = int(sample_rate)
        self.BLOCK_SIZE = int(block_size)
        self.ibuf = int(ibuf)

        self._volume = self._normalize_volume(volume)
        self._max_amplitude = int(max_amplitude)
        self._fade_ms = int(fade_ms)

        self.i2s = None
        self._i2s_rate = None
        self._tone_buf = None
        self._zero_buf = None

        if auto_init:
            self.iniciar()

    # =================================================
    # CONFIGURAÇÕES BÁSICAS
    # =================================================
    def _normalize_volume(self, value):
        if value is None:
            return self._volume if hasattr(self, "_volume") else 0.7

        try:
            value = float(value)
        except:
            value = 70.0

        if value < 0:
            value = 0
        if value > 100:
            value = 100

        return value / 100.0

    def set_volume(self, volume):
        self._volume = self._normalize_volume(volume)

    def volume(self, volume=None):
        """
        Uso simples:
            som.volume(60)  -> ajusta volume para 60%
            som.volume()    -> retorna volume atual
        """
        if volume is None:
            return self.get_volume()
        self.set_volume(volume)

    def get_volume(self):
        return int(self._volume * 100)

    def set_max_amplitude(self, amplitude):
        amplitude = int(amplitude)
        if amplitude < 0:
            amplitude = 0
        if amplitude > 32767:
            amplitude = 32767
        self._max_amplitude = amplitude

    def amplitude(self, amplitude=None):
        """
        Uso simples:
            som.amplitude(4000)
            som.amplitude()
        """
        if amplitude is None:
            return self._max_amplitude
        self.set_max_amplitude(amplitude)

    def get_i2s_info(self):
        return {
            "i2s_ativo": self.i2s is not None,
            "i2s_rate": self._i2s_rate,
            "sample_rate_padrao": self.SAMPLE_RATE,
            "block_size": self.BLOCK_SIZE,
            "ibuf": self.ibuf,
            "max_amplitude": self._max_amplitude,
            "volume_percent": self.get_volume()
        }

    def info(self):
        return self.get_i2s_info()

    # =================================================
    # I2S SOB DEMANDA
    # =================================================
    def iniciar(self, rate=None):
        if rate is None:
            rate = self.SAMPLE_RATE
        rate = int(rate)

        if self.i2s is not None and self._i2s_rate == rate:
            return

        self.deinit()

        # Tenta buffers menores se faltar memória.
        tentativas = [self.ibuf, 2048, 1024, 512]
        ultimo_erro = None

        for tamanho_ibuf in tentativas:
            try:
                gc.collect()
                self.i2s = I2S(
                    self.i2s_id,
                    sck=Pin(self.bclk),
                    ws=Pin(self.lrck),
                    sd=Pin(self.din),
                    mode=I2S.TX,
                    bits=16,
                    format=I2S.MONO,
                    rate=rate,
                    ibuf=int(tamanho_ibuf)
                )
                self._i2s_rate = rate
                self.ibuf = int(tamanho_ibuf)

                self._tone_buf = bytearray(2 * self.BLOCK_SIZE)
                self._zero_buf = bytearray(2 * self.BLOCK_SIZE)
                return

            except OSError as e:
                ultimo_erro = e
                self.i2s = None
                self._i2s_rate = None
                gc.collect()

        raise ultimo_erro

    def deinit(self, free_buffers=False):
        if self.i2s is not None:
            try:
                self.i2s.deinit()
            except:
                pass

        self.i2s = None
        self._i2s_rate = None

        if free_buffers:
            self._tone_buf = None
            self._zero_buf = None
            gc.collect()

    desligar = deinit

    # =================================================
    # SILÊNCIO / PAUSA
    # =================================================
    def silence(self, duration_ms):
        duration_ms = int(duration_ms)
        if duration_ms <= 0:
            return

        # Se o I2S ainda não foi iniciado, não precisa gastar memória.
        if self.i2s is None:
            time.sleep_ms(duration_ms)
            return

        total_samples = int(self._i2s_rate * duration_ms / 1000)
        sent = 0

        if self._zero_buf is None:
            self._zero_buf = bytearray(2 * self.BLOCK_SIZE)

        mv = memoryview(self._zero_buf)

        while sent < total_samples:
            self.i2s.write(mv)
            sent += self.BLOCK_SIZE

    pausa = silence
    pausar = silence

    # =================================================
    # TONS E NOTAS
    # =================================================
    def tone(self, freq, duration_ms, volume=None, fade_ms=None):
        """
        Toca uma frequência em Hz.
        Exemplo:
            som.tone(1000, 500)
            som.tom(1000, 500, 60)
        """
        if freq is None or freq <= 0:
            self.silence(duration_ms)
            return

        self.iniciar(self.SAMPLE_RATE)

        duration_ms = int(duration_ms)
        if duration_ms <= 0:
            return

        vol = self._normalize_volume(volume)
        amplitude = int(self._max_amplitude * vol)

        total_samples = int(self.SAMPLE_RATE * duration_ms / 1000)

        if fade_ms is None:
            fade_ms = self._fade_ms
        fade_samples = int(self.SAMPLE_RATE * int(fade_ms) / 1000)
        if fade_samples > total_samples // 2:
            fade_samples = total_samples // 2

        if self._tone_buf is None:
            self._tone_buf = bytearray(2 * self.BLOCK_SIZE)

        buf = self._tone_buf
        mv = memoryview(buf)

        phase = 0.0
        step = float(freq) / self.SAMPLE_RATE
        played = 0

        while played < total_samples:
            for i in range(self.BLOCK_SIZE):
                pos = played + i

                if pos >= total_samples:
                    sample = 0
                else:
                    env = 1.0

                    if fade_samples > 0:
                        if pos < fade_samples:
                            env = pos / fade_samples
                        elif pos >= total_samples - fade_samples:
                            env = (total_samples - pos - 1) / fade_samples

                    sample = int(amplitude * env * math.sin(2 * math.pi * phase))

                    phase += step
                    if phase >= 1.0:
                        phase -= 1.0

                buf[2 * i] = sample & 0xFF
                buf[2 * i + 1] = (sample >> 8) & 0xFF

            self.i2s.write(mv)
            played += self.BLOCK_SIZE

    tom = tone
    beep = tone

    def freq_nota(self, nota, oitava=None):
        """
        Converte nota musical para frequência.
        Aceita:
            "DO", "RE", "MI", "FA", "SOL", "LA", "SI"
            "DO4", "RE#4", "SOL3"
            "C4", "D#4", "A4"
            "P" ou "PAUSA" para silêncio
        """
        if nota is None:
            return 0

        nome = str(nota).strip().upper()
        nome = nome.replace("Ó", "O").replace("Á", "A").replace("É", "E")
        nome = nome.replace("Í", "I").replace("Ú", "U")

        if nome in self._REST_NAMES:
            return 0

        # Extrai oitava no final, se existir.
        oit = oitava
        if len(nome) > 0 and nome[-1].isdigit():
            oit = int(nome[-1])
            nome = nome[:-1]

        if oit is None:
            oit = 4

        # Acidente musical.
        acidente = 0
        if nome.endswith("#") or nome.endswith("S"):
            acidente = 1
            nome = nome[:-1]
        elif nome.endswith("B"):
            acidente = -1
            nome = nome[:-1]

        if nome not in self._NOTE_BASE:
            raise ValueError("Nota inválida: " + str(nota))

        semitom = self._NOTE_BASE[nome] + acidente

        # MIDI: C4 = 60, A4 = 69.
        midi = (int(oit) + 1) * 12 + semitom
        freq = 440.0 * (2 ** ((midi - 69) / 12))

        return int(freq + 0.5)

    def nota(self, nota, duracao_ms=400, volume=None, oitava=None, pausa_ms=0):
        """
        Comando simples para o aluno:
            som.nota("DO4", 500)
            som.nota("SOL", 300)
            som.nota("P", 200)
        """
        freq = self.freq_nota(nota, oitava)

        if freq <= 0:
            self.silence(duracao_ms)
        else:
            self.tone(freq, duracao_ms, volume)

        if pausa_ms > 0:
            self.silence(pausa_ms)

    def notas(self, sequencia, duracao_ms=350, volume=None, oitava=None, pausa_ms=40):
        """
        Toca várias notas com a mesma duração.
        Exemplo:
            som.notas(["DO4", "RE4", "MI4", "FA4"])
        """
        for n in sequencia:
            self.nota(n, duracao_ms, volume, oitava, pausa_ms)

    def musica(self, sequencia, tempo=120, volume=None, pausa_ms=40):
        """
        Toca uma melodia.

        Formas simples:
            som.musica(["DO4", "RE4", "MI4", "P", "MI4"])

        Com duração por nota:
            som.musica([("DO4", 300), ("RE4", 300), ("MI4", 600)])

        Com volume por nota:
            som.musica([("DO4", 300, 60), ("RE4", 300, 80)])
        """
        duracao_padrao = int(60000 / int(tempo))

        for item in sequencia:
            nota = item
            dur = duracao_padrao
            vol = volume

            if isinstance(item, tuple) or isinstance(item, list):
                if len(item) >= 1:
                    nota = item[0]
                if len(item) >= 2:
                    dur = int(item[1])
                if len(item) >= 3:
                    vol = item[2]

            self.nota(nota, dur, vol, pausa_ms=pausa_ms)

    melodia = musica
    tocar_musica = musica

    # =================================================
    # WAV DO ALUNO
    # =================================================
    def _read_u16(self, f):
        b = f.read(2)
        if len(b) != 2:
            raise ValueError("WAV incompleto")
        return b[0] | (b[1] << 8)

    def _read_u32(self, f):
        b = f.read(4)
        if len(b) != 4:
            raise ValueError("WAV incompleto")
        return b[0] | (b[1] << 8) | (b[2] << 16) | (b[3] << 24)

    def wav_info(self, caminho):
        """
        Lê informações básicas do WAV.
        Recomendado para alunos:
            WAV PCM, 16 bits, mono, 16000 Hz.
        Também aceita 8 bits e estéreo, convertendo para mono 16 bits.
        """
        with open(caminho, "rb") as f:
            if f.read(4) != b"RIFF":
                raise ValueError("Arquivo não é RIFF/WAV")
            f.read(4)  # tamanho
            if f.read(4) != b"WAVE":
                raise ValueError("Arquivo não é WAV")

            info = {
                "audio_format": None,
                "channels": None,
                "sample_rate": None,
                "bits": None,
                "data_start": None,
                "data_size": None
            }

            while True:
                chunk_id = f.read(4)
                if len(chunk_id) < 4:
                    break

                chunk_size = self._read_u32(f)
                chunk_start = f.tell()

                if chunk_id == b"fmt ":
                    info["audio_format"] = self._read_u16(f)
                    info["channels"] = self._read_u16(f)
                    info["sample_rate"] = self._read_u32(f)
                    f.read(6)  # byte_rate + block_align
                    info["bits"] = self._read_u16(f)

                elif chunk_id == b"data":
                    info["data_start"] = f.tell()
                    info["data_size"] = chunk_size
                    f.seek(chunk_size, 1)

                else:
                    f.seek(chunk_size, 1)

                # Chunks WAV podem ter padding de 1 byte.
                if chunk_size % 2 == 1:
                    f.seek(1, 1)

                if info["sample_rate"] is not None and info["data_start"] is not None:
                    break

                # Garante que pulou o chunk inteiro mesmo após leituras parciais.
                atual = f.tell()
                esperado = chunk_start + chunk_size + (chunk_size % 2)
                if atual < esperado:
                    f.seek(esperado)

        if info["audio_format"] != 1:
            raise ValueError("Use WAV PCM sem compressão")
        if info["channels"] not in (1, 2):
            raise ValueError("Use WAV mono ou estéreo")
        if info["bits"] not in (8, 16):
            raise ValueError("Use WAV 8 bits ou 16 bits")
        if info["data_start"] is None:
            raise ValueError("Chunk de áudio não encontrado")

        return info

    def _pcm16_volume_inplace(self, buf, n, volume_percent):
        limite = n - (n % 2)

        if volume_percent >= 100:
            return limite

        for i in range(0, limite, 2):
            sample = buf[i] | (buf[i + 1] << 8)
            if sample >= 32768:
                sample -= 65536

            sample = (sample * volume_percent) // 100

            if sample > 32767:
                sample = 32767
            elif sample < -32768:
                sample = -32768

            if sample < 0:
                sample += 65536

            buf[i] = sample & 0xFF
            buf[i + 1] = (sample >> 8) & 0xFF

        return limite

    def _convert_wav_block(self, in_buf, n, out_buf, channels, bits, volume_percent):
        """
        Converte WAV 8/16 bits mono/estéreo para PCM 16 bits mono.
        Retorna quantidade de bytes válidos em out_buf.
        """
        if bits == 16 and channels == 1:
            limite = self._pcm16_volume_inplace(in_buf, n, volume_percent)
            return in_buf, limite

        out_i = 0

        if bits == 16 and channels == 2:
            limite = n - (n % 4)

            for i in range(0, limite, 4):
                l = in_buf[i] | (in_buf[i + 1] << 8)
                r = in_buf[i + 2] | (in_buf[i + 3] << 8)

                if l >= 32768:
                    l -= 65536
                if r >= 32768:
                    r -= 65536

                sample = ((l + r) // 2) * volume_percent // 100

                if sample > 32767:
                    sample = 32767
                elif sample < -32768:
                    sample = -32768

                if sample < 0:
                    sample += 65536

                out_buf[out_i] = sample & 0xFF
                out_buf[out_i + 1] = (sample >> 8) & 0xFF
                out_i += 2

        elif bits == 8 and channels == 1:
            for i in range(n):
                sample = (int(in_buf[i]) - 128) * 256
                sample = sample * volume_percent // 100

                if sample < 0:
                    sample += 65536

                out_buf[out_i] = sample & 0xFF
                out_buf[out_i + 1] = (sample >> 8) & 0xFF
                out_i += 2

        elif bits == 8 and channels == 2:
            limite = n - (n % 2)

            for i in range(0, limite, 2):
                l = int(in_buf[i]) - 128
                r = int(in_buf[i + 1]) - 128
                sample = ((l + r) // 2) * 256
                sample = sample * volume_percent // 100

                if sample < 0:
                    sample += 65536

                out_buf[out_i] = sample & 0xFF
                out_buf[out_i + 1] = (sample >> 8) & 0xFF
                out_i += 2

        return out_buf, out_i

    def wav(self, caminho, volume=None, repetir=1, mostrar=False):
        """
        Toca WAV do aluno.

        Comando simples:
            som.wav("/sons/aluno.wav")

        Com volume:
            som.wav("/sons/aluno.wav", 60)

        Recomendado:
            WAV PCM, 16 bits, mono, 16000 Hz.
        """
        vol_percent = int(self._normalize_volume(volume) * 100)
        info = self.wav_info(caminho)

        if mostrar:
            print(info)

        rate = int(info["sample_rate"])
        channels = int(info["channels"])
        bits = int(info["bits"])
        data_start = int(info["data_start"])
        data_size = int(info["data_size"])

        self.iniciar(rate)

        # 1024 é seguro para ESP32 e não consome muita RAM.
        in_buf = bytearray(1024)
        out_buf = bytearray(2048)
        in_mv = memoryview(in_buf)
        out_mv = memoryview(out_buf)

        for _ in range(int(repetir)):
            with open(caminho, "rb") as f:
                f.seek(data_start)
                restante = data_size

                while restante > 0:
                    qtd = 1024
                    if restante < qtd:
                        qtd = restante

                    n = f.readinto(in_mv[:qtd])
                    if not n:
                        break

                    restante -= n

                    saida, n_saida = self._convert_wav_block(
                        in_buf, n, out_buf, channels, bits, vol_percent
                    )

                    if n_saida > 0:
                        if saida is in_buf:
                            self.i2s.write(in_mv[:n_saida])
                        else:
                            self.i2s.write(out_mv[:n_saida])

        self.silence(40)

    tocar_wav = wav
    som_wav = wav
    audio = wav

    # =================================================
    # SONS PRONTOS / COMPATIBILIDADE
    # =================================================
    def click(self, volume=None):
        self.press(volume)

    def ok(self, volume=None):
        self.system_ok(volume)

    def fail(self, volume=None):
        self.error(volume)

    def boot(self, volume=None):
        self.power_on(volume)

    def press(self, volume=None):
        self.tone(1200, 18, volume)
        self.silence(10)

    def error(self, volume=None):
        for _ in range(2):
            self.sweep(1500, 350, 240, steps=22, volume=volume)
            self.silence(35)

    def power_low(self, volume=None):
        self.musica([
            ("SOL3", 140),
            ("SOL3", 140),
            ("SOL3", 220)
        ], volume=volume, pausa_ms=80)

    def system_ok(self, volume=None):
        self.musica([
            ("DO5", 60),
            ("MI5", 70),
            ("SOL5", 90)
        ], volume=volume, pausa_ms=20)

    def run_start(self, volume=None):
        self.musica([
            ("MI4", 70),
            ("SOL4", 70),
            ("DO5", 80),
            ("MI5", 100)
        ], volume=volume, pausa_ms=15)

    def run_stop(self, volume=None):
        self.musica([
            ("MI5", 70),
            ("DO5", 70),
            ("SOL4", 80),
            ("MI4", 120)
        ], volume=volume, pausa_ms=15)

    def power_on(self, volume=None):
        self.sweep(500, 1500, 180, steps=18, volume=volume)
        self.silence(20)
        self.system_ok(volume)

    def power_off(self, volume=None):
        self.sweep(1500, 350, 220, steps=24, volume=volume)
        self.silence(20)
        self.tone(260, 120, volume)

    def sweep(self, start, end, duration_ms, steps=24, volume=None):
        if steps < 1:
            steps = 1

        freq = float(start)
        delta = (float(end) - float(start)) / steps
        chunk = max(1, int(duration_ms / steps))

        for _ in range(steps):
            self.tone(int(freq), chunk, volume)
            freq += delta

    def sweep_up(self, start=600, end=1800, step=50, duration_ms=10, volume=None):
        if step <= 0:
            step = 50
        f = start
        while f < end:
            self.tone(f, duration_ms, volume)
            f += step

    def sweep_down(self, start=1800, end=600, step=50, duration_ms=10, volume=None):
        if step <= 0:
            step = 50
        f = start
        while f > end:
            self.tone(f, duration_ms, volume)
            f -= step

    def warble(self, f1, f2, cycles=10, on_ms=50, off_ms=0, volume=None):
        for i in range(cycles):
            self.tone(f1 if (i % 2 == 0) else f2, on_ms, volume)
            if off_ms > 0:
                self.silence(off_ms)

    def rb_move(self, volume=None):
        seq = [180, 220, 200, 240]
        total = 0
        idx = 0
        slot = 48

        while total < 4000:
            self.tone(seq[idx % len(seq)], 22, volume)
            self.silence(slot - 22)
            idx += 1
            total += slot

    def rb_speaker(self, volume=None):
        total = 0
        slot = 37
        freqs = [700, 920]
        i = 0

        while total < 2000:
            self.tone(freqs[i % 2], slot, volume)
            i += 1
            total += slot

    def rb_fire(self, volume=None):
        for _ in range(2):
            self.sweep(900, 1800, 500, steps=16, volume=volume)
            self.sweep(1800, 900, 500, steps=16, volume=volume)

    def rb_escape(self, volume=None):
        for _ in range(4):
            self.musica([
                ("DO4", 45),
                ("SOL4", 45),
                ("RE5", 60)
            ], volume=volume, pausa_ms=10)
            self.silence(30)

    def rb_dog(self, volume=None):
        for _ in range(3):
            self.musica([
                ("MI3", 75),
                ("RE4", 55),
                ("DO3", 70)
            ], volume=volume, pausa_ms=20)
            self.silence(50)

    def rb_cat(self, volume=None):
        self.sweep(1400, 650, 520, steps=20, volume=volume)
        self.silence(50)
        self.sweep(900, 420, 360, steps=14, volume=volume)

    def rb_bird(self, volume=None):
        self.musica([
            ("DO6", 35),
            ("MI6", 35),
            ("SOL6", 35),
            ("MI6", 35)
        ], volume=volume, pausa_ms=10)

    def rb_victory(self, volume=None):
        frase = [
            ("DO5", 140),
            ("MI5", 140),
            ("SOL5", 180),
            ("MI5", 120),
            ("SOL5", 160),
            ("DO6", 260)
        ]

        for _ in range(3):
            self.musica(frase, volume=volume, pausa_ms=20)

        self.musica([
            ("SOL5", 180),
            ("SI5", 180),
            ("DO6", 420)
        ], volume=volume, pausa_ms=25)

    def rb_fail(self, volume=None):
        for _ in range(2):
            self.musica([
                ("LA5", 220),
                ("FA5", 220),
                ("RE5", 280),
                ("DO5", 380)
            ], volume=volume, pausa_ms=30)

        self.sweep(700, 250, 900, steps=24, volume=volume)

    def music1(self, volume=None):
        frase = [
            ("DO5", 180),
            ("MI5", 180),
            ("SOL5", 180),
            ("MI5", 180),
            ("RE5", 180),
            ("FA5", 180),
            ("LA5", 260),
            ("SOL5", 160),
            ("MI5", 160),
            ("RE5", 180),
            ("DO5", 320),
        ]

        for _ in range(3):
            self.musica(frase, volume=volume, pausa_ms=20)

        self.musica([
            ("MI5", 180),
            ("SOL5", 180),
            ("DO6", 500),
            ("SOL5", 240),
            ("DO5", 500)
        ], volume=volume, pausa_ms=20)

    def play(self, sound_id, volume=None):
        if sound_id == self.SOUND_PRESS:
            self.press(volume)
        elif sound_id == self.SOUND_ERROR:
            self.error(volume)
        elif sound_id == self.SOUND_POWER_LOW:
            self.power_low(volume)
        elif sound_id == self.SOUND_OK:
            self.system_ok(volume)
        elif sound_id == self.SOUND_RUN_START:
            self.run_start(volume)
        elif sound_id == self.SOUND_RUN_STOP:
            self.run_stop(volume)
        elif sound_id == self.SOUND_POWER_ON:
            self.power_on(volume)
        elif sound_id == self.SOUND_POWER_OFF:
            self.power_off(volume)
        elif sound_id == self.SOUND_RB_MOVE:
            self.rb_move(volume)
        elif sound_id == self.SOUND_RB_SPEAKER:
            self.rb_speaker(volume)
        elif sound_id == self.SOUND_RB_FIRE:
            self.rb_fire(volume)
        elif sound_id == self.SOUND_RB_ESCAPE:
            self.rb_escape(volume)
        elif sound_id == self.SOUND_RB_DOG:
            self.rb_dog(volume)
        elif sound_id == self.SOUND_RB_CAT:
            self.rb_cat(volume)
        elif sound_id == self.SOUND_RB_BIRD:
            self.rb_bird(volume)
        elif sound_id == self.SOUND_RB_VICTORY:
            self.rb_victory(volume)
        elif sound_id == self.SOUND_RB_FAIL:
            self.rb_fail(volume)
        elif sound_id == self.SOUND_MUSIC1:
            self.music1(volume)


# -------------------------------------------------
# Aliases estilo define
# -------------------------------------------------
Sound_Press      = MihuSound.SOUND_PRESS
Sound_Error      = MihuSound.SOUND_ERROR
Sound_PowerLow   = MihuSound.SOUND_POWER_LOW
Sound_Ok         = MihuSound.SOUND_OK
Sound_RunStart   = MihuSound.SOUND_RUN_START
Sound_RunStop    = MihuSound.SOUND_RUN_STOP
Sound_PowerOn    = MihuSound.SOUND_POWER_ON
Sound_PowerOff   = MihuSound.SOUND_POWER_OFF
Sound_RbMove     = MihuSound.SOUND_RB_MOVE
Sound_RbSpeaker  = MihuSound.SOUND_RB_SPEAKER
Sound_RbFire     = MihuSound.SOUND_RB_FIRE
Sound_RbEscape   = MihuSound.SOUND_RB_ESCAPE
Sound_RbDog      = MihuSound.SOUND_RB_DOG
Sound_RbCat      = MihuSound.SOUND_RB_CAT
Sound_RbBird     = MihuSound.SOUND_RB_BIRD
Sound_RbVictory  = MihuSound.SOUND_RB_VICTORY
Sound_RbFail     = MihuSound.SOUND_RB_FAIL
Sound_Music1     = MihuSound.SOUND_MUSIC1


# -------------------------------------------------
# Instância global segura: não inicia I2S no import.
# -------------------------------------------------
mihuSound = MihuSound()
som = mihuSound
sound = mihuSound

# Comandos de módulo para ficar simples para o aluno.
nota = som.nota
notas = som.notas
musica = som.musica
melodia = som.melodia
tom = som.tom
beep = som.beep
wav = som.wav
tocar_wav = som.tocar_wav
volume = som.volume
amplitude = som.amplitude
pausa = som.pausa
