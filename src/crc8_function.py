import crc8
from binascii import unhexlify


def crc8Calculate(cmdInput):
    cmdInput = unhexlify(cmdInput)
    hash = crc8.crc8()
    hash.update(cmdInput)
    crc8Frame = hash.digest()
    HashedInput = cmdInput + crc8Frame
    return HashedInput


def crc8InjectErr(cmdInput):
    cmdInput += "05"
    cmdInput = unhexlify(cmdInput)
    return cmdInput
