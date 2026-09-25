# ============================================================
# MIHU TEST - INTERNATIONALIZATION
# ============================================================
#
# Idiomas:
#   ZH = Chinese (Simplified)
#   EN = English
#   ES = Spanish
#   PT = Portuguese
#
# Os identificadores do protocolo serial permanecem em inglês
# para não quebrar a integração com o software de testes.
# ============================================================

LANGUAGES = (
    ("ZH", "中文"),
    ("EN", "English"),
    ("ES", "Espanol"),
    ("PT", "Portugues"),
)

_current_language = "EN"


_TRANSLATIONS = {
    "EN": {
        "language": "LANGUAGE",
        "test_title": "MIHU TEST",
        "full_test": "FULL TEST",
        "board_test": "BOARD TEST",
        "peripheral_test": "PERIPHERAL TEST",
        "report": "REPORT",

        "board_ihm": "IHM BOARD",
        "board_led": "LED BOARD",
        "board_base": "BASE BOARD",
        "board_core": "CORE BOARD",

        "test_report": "TEST REPORT",
        "pass": "PASS",
        "fail": "FAIL",
        "pending": "PENDING",
        "not_implemented": "NOT IMPLEMENTED",
        "back_return": "BACK TO RETURN",
        "no_items": "NO ITEMS",

        "factory_service": "FACTORY / SERVICE",
        "starting": "STARTING...",

        "display": "DISPLAY",
        "buttons": "BUTTONS",
        "rfid": "RFID",
        "light_left": "LIGHT LEFT",
        "light_right": "LIGHT RIGHT",
        "leds": "LEDS",
        "sound": "SOUND",
        "gyroscope": "GYROSCOPE",
        "sd_card": "SD CARD",
        "rj_sensors": "RJ SENSORS",
        "rj_motors": "RJ MOTORS",
        "ads_battery": "ADS BATTERY",
        "ads_motors": "ADS MOTORS",
        "pca_leds": "PCA LEDS",
        "ir_led": "IR LED",
        "remote_control": "REMOTE IR",

        "display_test": "DISPLAY TEST",
        "full_white": "FULL WHITE SCREEN",
        "check_dead_pixels": "CHECK DEAD PIXELS",
        "image_ok": "IMAGE OK?",
        "ok_pass": "OK = PASS",
        "back_fail": "BACK = FAIL",

        "button_test": "BUTTON TEST",
        "press": "PRESS:",

        "rfid_test": "RFID TEST",
        "present_card": "PRESENT CARD",
        "waiting": "WAITING...",

        "sound_test": "SOUND TEST",
        "listen": "LISTEN...",
        "heard_sound": "DID YOU HEAR IT?",

        "pass_short": "PASS",
        "fail_short": "FAIL",

        "light_test": "LIGHT SENSOR TEST",
        "left_sensor": "LEFT SENSOR",
        "right_sensor": "RIGHT SENSOR",
        "change_light": "CHANGE THE LIGHT",
        "cover_or_light": "COVER OR ILLUMINATE",
        "baseline": "BASE",
        "current": "NOW",
        "delta": "DELTA",
        "sensor_not_found": "SENSOR NOT FOUND",
        "sensor_no_response": "NO LIGHT CHANGE",
        "sensor_detected": "LIGHT CHANGE OK",
    },

    "ES": {
        "language": "IDIOMA",
        "test_title": "PRUEBA MIHU",
        "full_test": "PRUEBA COMPLETA",
        "board_test": "PRUEBA DE PLACA",
        "peripheral_test": "PERIFERICOS",
        "report": "INFORME",

        "board_ihm": "PLACA IHM",
        "board_led": "PLACA LED",
        "board_base": "PLACA BASE",
        "board_core": "PLACA CORE",

        "test_report": "INFORME PRUEBAS",
        "pass": "APROBADO",
        "fail": "FALLO",
        "pending": "PENDIENTE",
        "not_implemented": "NO IMPLEMENTADO",
        "back_return": "BACK PARA VOLVER",
        "no_items": "SIN ELEMENTOS",

        "factory_service": "FABRICA / SERVICIO",
        "starting": "INICIANDO...",

        "display": "PANTALLA",
        "buttons": "BOTONES",
        "rfid": "RFID",
        "light_left": "LUZ IZQUIERDA",
        "light_right": "LUZ DERECHA",
        "leds": "LEDS",
        "sound": "SONIDO",
        "gyroscope": "GIROSCOPIO",
        "sd_card": "TARJETA SD",
        "rj_sensors": "RJ SENSORES",
        "rj_motors": "RJ MOTORES",
        "ads_battery": "ADS BATERIA",
        "ads_motors": "ADS MOTORES",
        "pca_leds": "PCA LEDS",
        "ir_led": "LED IR",
        "remote_control": "CONTROL IR",

        "display_test": "PRUEBA PANTALLA",
        "full_white": "PANTALLA BLANCA",
        "check_dead_pixels": "BUSCAR PIXEL MUERTO",
        "image_ok": "IMAGEN CORRECTA?",
        "ok_pass": "OK = APROBADO",
        "back_fail": "BACK = FALLO",

        "button_test": "PRUEBA BOTONES",
        "press": "PRESIONE:",

        "rfid_test": "PRUEBA RFID",
        "present_card": "ACERQUE TARJETA",
        "waiting": "ESPERANDO...",

        "sound_test": "PRUEBA SONIDO",
        "listen": "ESCUCHE...",
        "heard_sound": "ESCUCHO EL SONIDO?",

        "pass_short": "APROBADO",
        "fail_short": "FALLO",

        "light_test": "PRUEBA SENSOR LUZ",
        "left_sensor": "SENSOR IZQUIERDO",
        "right_sensor": "SENSOR DERECHO",
        "change_light": "CAMBIE LA LUZ",
        "cover_or_light": "CUBRA O ILUMINE",
        "baseline": "BASE",
        "current": "AHORA",
        "delta": "CAMBIO",
        "sensor_not_found": "SENSOR NO ENCONTRADO",
        "sensor_no_response": "SIN CAMBIO DE LUZ",
        "sensor_detected": "CAMBIO DE LUZ OK",
    },

    "PT": {
        "language": "IDIOMA",
        "test_title": "TESTE MIHU",
        "full_test": "TESTE COMPLETO",
        "board_test": "TESTE POR PLACA",
        "peripheral_test": "PERIFERICOS",
        "report": "RELATORIO",

        "board_ihm": "PLACA IHM",
        "board_led": "PLACA LED",
        "board_base": "PLACA BASE",
        "board_core": "PLACA CORE",

        "test_report": "RELATORIO TESTES",
        "pass": "APROVADO",
        "fail": "FALHA",
        "pending": "PENDENTE",
        "not_implemented": "NAO IMPLEMENTADO",
        "back_return": "BACK PARA VOLTAR",
        "no_items": "SEM ITENS",

        "factory_service": "FABRICA / MANUTENCAO",
        "starting": "INICIANDO...",

        "display": "DISPLAY",
        "buttons": "BOTOES",
        "rfid": "RFID",
        "light_left": "LUZ ESQUERDA",
        "light_right": "LUZ DIREITA",
        "leds": "LEDS",
        "sound": "SOM",
        "gyroscope": "GIROSCOPIO",
        "sd_card": "CARTAO SD",
        "rj_sensors": "RJ SENSORES",
        "rj_motors": "RJ MOTORES",
        "ads_battery": "ADS BATERIA",
        "ads_motors": "ADS MOTORES",
        "pca_leds": "PCA LEDS",
        "ir_led": "LED IR",
        "remote_control": "CONTROLE IR",

        "display_test": "TESTE DISPLAY",
        "full_white": "TELA TODA BRANCA",
        "check_dead_pixels": "VERIFIQUE PIXELS",
        "image_ok": "IMAGEM CORRETA?",
        "ok_pass": "OK = APROVADO",
        "back_fail": "BACK = FALHA",

        "button_test": "TESTE BOTOES",
        "press": "PRESSIONE:",

        "rfid_test": "TESTE RFID",
        "present_card": "APROXIME CARTAO",
        "waiting": "AGUARDANDO...",

        "sound_test": "TESTE SOM",
        "listen": "ESCUTE...",
        "heard_sound": "OUVIU O SOM?",

        "pass_short": "APROVADO",
        "fail_short": "FALHA",

        "light_test": "TESTE SENSOR LUZ",
        "left_sensor": "SENSOR ESQUERDO",
        "right_sensor": "SENSOR DIREITO",
        "change_light": "MUDE A LUZ",
        "cover_or_light": "CUBRA OU ILUMINE",
        "baseline": "BASE",
        "current": "AGORA",
        "delta": "VARIACAO",
        "sensor_not_found": "SENSOR NAO ENCONTRADO",
        "sensor_no_response": "SEM VARIACAO DE LUZ",
        "sensor_detected": "VARIACAO DE LUZ OK",
    },

    "ZH": {
        "language": "语言",
        "test_title": "MIHU 测试",
        "full_test": "完整测试",
        "board_test": "板卡测试",
        "peripheral_test": "外设测试",
        "report": "报告",

        "board_ihm": "IHM 板卡",
        "board_led": "LED 板卡",
        "board_base": "底板",
        "board_core": "核心板",

        "test_report": "测试报告",
        "pass": "通过",
        "fail": "失败",
        "pending": "待测试",
        "not_implemented": "未实现",
        "back_return": "BACK 返回",
        "no_items": "无项目",

        "factory_service": "工厂 / 维修",
        "starting": "启动中...",

        "display": "显示屏",
        "buttons": "按键",
        "rfid": "RFID",
        "light_left": "左光感",
        "light_right": "右光感",
        "leds": "LED",
        "sound": "声音",
        "gyroscope": "陀螺仪",
        "sd_card": "SD 卡",
        "rj_sensors": "RJ 传感器",
        "rj_motors": "RJ 电机",
        "ads_battery": "ADS 电池",
        "ads_motors": "ADS 电机",
        "pca_leds": "PCA LED",
        "ir_led": "红外 LED",
        "remote_control": "红外遥控",

        "display_test": "显示屏测试",
        "full_white": "全白屏",
        "check_dead_pixels": "检查坏点",
        "image_ok": "图像正常?",
        "ok_pass": "OK = 通过",
        "back_fail": "BACK = 失败",

        "button_test": "按键测试",
        "press": "按下:",

        "rfid_test": "RFID 测试",
        "present_card": "放置卡片",
        "waiting": "等待中...",

        "sound_test": "声音测试",
        "listen": "请听...",
        "heard_sound": "听到声音?",

        "pass_short": "通过",
        "fail_short": "失败",

        "light_test": "光线传感器测试",
        "left_sensor": "左侧传感器",
        "right_sensor": "右侧传感器",
        "change_light": "改变光线",
        "cover_or_light": "遮挡或照亮",
        "baseline": "基准",
        "current": "当前",
        "delta": "变化",
        "sensor_not_found": "未找到传感器",
        "sensor_no_response": "光线无变化",
        "sensor_detected": "光线变化正常",
    },
}


_TEST_KEYS = {
    "DISPLAY": "display",
    "BUTTONS": "buttons",
    "RFID": "rfid",
    "LIGHT_LEFT": "light_left",
    "LIGHT_RIGHT": "light_right",
    "LEDS": "leds",
    "SOUND": "sound",
    "GYROSCOPE": "gyroscope",
    "SD_CARD": "sd_card",
    "RJ_SENSORS": "rj_sensors",
    "RJ_MOTORS": "rj_motors",
    "ADS_BATTERY": "ads_battery",
    "ADS_MOTORS": "ads_motors",
    "PCA_LEDS": "pca_leds",
    "IR_LED": "ir_led",
    "REMOTE_CONTROL": "remote_control",
}


_MESSAGE_KEYS = {
    "No dead pixels detected.": "pass",
    "Display pixel failure.": "fail",
    "Display test timeout.": "fail",
    "All buttons detected.": "pass",
    "Button test timeout.": "fail",
    "Card detected.": "pass",
    "RFID timeout.": "fail",
    "RFID error.": "fail",
    "Sound validated.": "pass",
    "Sound rejected.": "fail",
    "Sound test timeout.": "fail",
    "Test timeout.": "fail",
    "Test not implemented.": "not_implemented",
    "Light sensor not found.": "sensor_not_found",
    "No light change detected.": "sensor_no_response",
    "Light change detected.": "sensor_detected",
}


def set_language(code):
    global _current_language

    code = str(code).strip().upper()

    if code not in _TRANSLATIONS:
        code = "EN"

    _current_language = code
    return code


def language():
    return _current_language


def t(key, default=None):
    key = str(key)

    table = _TRANSLATIONS.get(
        _current_language,
        _TRANSLATIONS["EN"],
    )

    if key in table:
        return table[key]

    if key in _TRANSLATIONS["EN"]:
        return _TRANSLATIONS["EN"][key]

    if default is not None:
        return default

    return key


def test_label(name):
    name = str(name).upper()
    key = _TEST_KEYS.get(name)

    if key is None:
        return name

    return t(key, name)


def board_label(board):
    board = str(board).upper()

    keys = {
        "IHM": "board_ihm",
        "LED": "board_led",
        "BASE": "board_base",
        "CORE": "board_core",
    }

    key = keys.get(board)

    if key is None:
        return board

    return t(key, board)


def result_message(message):
    if not message:
        return ""

    key = _MESSAGE_KEYS.get(
        str(message)
    )

    if key is not None:
        return t(key)

    text = str(message)

    if text.startswith("Timeout on "):
        return t("fail") + ": " + text[11:]

    return text
