# constants.py
# Constantes compartilhadas da biblioteca mihuSensor3.

RESET = 0
STARTED = 1
DATA_MODE = 2

UART = "UART"
BOTAO = "BOTAO"
SOM = "SOM"
VAZIO = "VAZIO"
INDEFINIDO = "INDEFINIDO"

COLOR = "COLOR"
ULTRASONIC = "ULTRASONIC"
GYRO = "GYRO"
INFRARED = "INFRARED"
BUTTON = "BUTTON"
SOUND = "SOUND"
EMPTY = "EMPTY"
UNKNOWN = "UNKNOWN"

TYPE_COLOR = 29
TYPE_ULTRASONIC = 30
TYPE_GYRO = 32
TYPE_INFRARED = 33

UART_TYPE_NAMES = {
    TYPE_COLOR: COLOR,
    TYPE_ULTRASONIC: ULTRASONIC,
    TYPE_GYRO: GYRO,
    TYPE_INFRARED: INFRARED,
}

# Sensor de cor.
REFLEXAO = 0
AMBIENTE = 1
COR = 2

SEM_COR = 0
PRETO = 1
AZUL = 2
VERDE = 3
AMARELO = 4
VERMELHO = 5
BRANCO = 6
MARROM = 7

# Ultrassônico.
CM = 0
POLEGADAS = 1
ESCUTA = 2

# Giroscópio.
ANGULO = 0
VELOCIDADE = 1
ANGULO_VELOCIDADE = 3

# Infravermelho.
PROXIMIDADE = 0
BUSCA = 1
CONTROLE = 2

MAX_MODES = 10
MAX_DATA_ITEMS = 10

HEART_BEAT_MS = 100
UART_DATA_TIMEOUT_MS = 700
UART_HANDSHAKE_TIMEOUT_MS = 2500

# Tempo máximo esperando o primeiro TYPE depois de abrir a UART
# em 2400 baud. O log real mostrou TYPE chegando perto de 2 s;
# 2600 ms dá margem sem confundir uma inicialização lenta com falha.
UART_TYPE_TIMEOUT_MS = 2600

# Durante a primeira conexão física, uma falha de inicialização pode
# provocar no máximo UMA reinicialização lógica da UART. Depois disso
# o serviço não entra em loop de reset. Uma nova conexão física zera
# este contador.
UART_INITIAL_RETRY_MAX = 1

# Requisito físico do handshake EV3 UART. A espera é
# controlada por estado, sem sleep_ms().
UART_BAUD_SWITCH_MS = 100

LEITURA_TIMEOUT_MS = 3000

# Validação elétrica de conexão.
#
# Não é média nem filtragem da leitura do sensor. A biblioteca
# continua lendo somente uma amostra ADC por atualização.
#
# Este tempo apenas impede que um pulso isolado causado por
# mau contato habilite a UART.
ADC_CONNECTION_STABLE_MS = 30

# Uma UART já reconhecida não é desmontada por leituras
# intermediárias como 48, 80 ou 144. Para desligar uma UART
# ativa pelo ADC, a porta precisa permanecer realmente VAZIA
# durante este tempo.
ADC_UART_EMPTY_STABLE_MS = 20

# Janela executada antes do programa do aluno. Serve
# para perceber sensores que ainda estão iniciando
# eletricamente durante o boot.
BOOT_DISCOVERY_MS = 300
BOOT_TIMEOUT_MS = 4500

# Interface pública do ADC.
ADC_PUBLIC_MIN = 0
ADC_PUBLIC_MAX = 4095

# Mediana progressiva curta. Mantém o comportamento usado no
# diagnóstico 5.5.x sem inserir qualquer delay.
ADC_FILTER_SAMPLES = 5

# A classificação elétrica usa a escala histórica 0..65535
# para manter os limiares já calibrados.
ADC_UART_MIN = 0
ADC_UART_MAX = 99

ADC_BOTAO_MIN = 100
ADC_BOTAO_MAX = 700

ADC_SOM_MIN = 1100
ADC_SOM_MAX = 17500

ADC_VAZIO_MIN = 60000

SEM_DELAY = True

# =====================================================
# ============== SETE PORTAS / ADS1115 ================
# =====================================================

# Existem somente três controladores UART físicos.
MAX_UART_SENSORS = 3
UART_SEM_RECURSO = "UART_SEM_RECURSO"

# ADS1115 compartilhado entre M1, M2, M3 e M4.
ADS1115_I2C_ID = 0
ADS1115_SDA = 39
ADS1115_SCL = 40
ADS1115_FREQ = 400000
ADS1115_ADDRESS = 0x48

ADS1115_M1_CHANNEL = 0
ADS1115_M2_CHANNEL = 1
ADS1115_M3_CHANNEL = 2
ADS1115_M4_CHANNEL = 3

# Faixas calibradas do ADS1115 em leitura single-ended.
ADS_ADC_UART_MIN = 0
ADS_ADC_UART_MAX = 750

ADS_ADC_BOTAO_MIN = 800
ADS_ADC_BOTAO_MAX = 1600

ADS_ADC_SOM_MIN = 1650
ADS_ADC_SOM_MAX = 11400

ADS_ADC_VAZIO_MIN = 11500

ADC_SOURCE_INTERNAL = "ADC_INTERNO"
ADC_SOURCE_ADS1115 = "ADS1115"

# 860 SPS = 1163 us por conversao. Margem sem bloqueio.
ADS1115_CONVERSION_US = 1250
