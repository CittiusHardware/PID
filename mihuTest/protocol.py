try:
    import ujson as json
except ImportError:
    import json


def send(data):
    try:
        print(json.dumps(data))
    except Exception as error:
        print(
            '{"type":"ERROR","message":"JSON_ERROR","detail":"'
            + str(error).replace('"', "'")
            + '"}'
        )


def ready(version):
    send({
        "type": "READY",
        "device": "MIHU-S3",
        "firmware": "MIHU_TEST",
        "version": version,
    })


def running(name):
    send({
        "type": "TEST_RUNNING",
        "test": name,
    })


def result(test_result):
    send({
        "type": "TEST_RESULT",
        "result": test_result.to_dict(),
    })


def report(state):
    send({
        "type": "REPORT",
        "report": state.to_dict(),
    })


def message(text, level="INFO"):
    send({
        "type": "MESSAGE",
        "level": level,
        "message": text,
    })
