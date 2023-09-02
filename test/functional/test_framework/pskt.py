#!/usr/bin/env python3
# Copyright (c) 2022 The Bitcoin Core developers
# Copyright (c) 2023-2023 The Koyotecoin Core developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or http://www.opensource.org/licenses/mit-license.php.

import base64

from .messages import (
    CTransaction,
    deser_string,
    from_binary,
    ser_compact_size,
)


# global types
PSKT_GLOBAL_UNSIGNED_TX = 0x00
PSKT_GLOBAL_XPUB = 0x01
PSKT_GLOBAL_TX_VERSION = 0x02
PSKT_GLOBAL_FALLBACK_LOCKTIME = 0x03
PSKT_GLOBAL_INPUT_COUNT = 0x04
PSKT_GLOBAL_OUTPUT_COUNT = 0x05
PSKT_GLOBAL_TX_MODIFIABLE = 0x06
PSKT_GLOBAL_VERSION = 0xfb
PSKT_GLOBAL_PROPRIETARY = 0xfc

# per-input types
PSKT_IN_NON_WITNESS_UTXO = 0x00
PSKT_IN_WITNESS_UTXO = 0x01
PSKT_IN_PARTIAL_SIG = 0x02
PSKT_IN_SIGHASH_TYPE = 0x03
PSKT_IN_REDEEM_SCRIPT = 0x04
PSKT_IN_WITNESS_SCRIPT = 0x05
PSKT_IN_BIP32_DERIVATION = 0x06
PSKT_IN_FINAL_SCRIPTSIG = 0x07
PSKT_IN_FINAL_SCRIPTWITNESS = 0x08
PSKT_IN_POR_COMMITMENT = 0x09
PSKT_IN_RIPEMD160 = 0x0a
PSKT_IN_SHA256 = 0x0b
PSKT_IN_HASH160 = 0x0c
PSKT_IN_HASH256 = 0x0d
PSKT_IN_PREVIOUS_TXID = 0x0e
PSKT_IN_OUTPUT_INDEX = 0x0f
PSKT_IN_SEQUENCE = 0x10
PSKT_IN_REQUIRED_TIME_LOCKTIME = 0x11
PSKT_IN_REQUIRED_HEIGHT_LOCKTIME = 0x12
PSKT_IN_TAP_KEY_SIG = 0x13
PSKT_IN_TAP_SCRIPT_SIG = 0x14
PSKT_IN_TAP_LEAF_SCRIPT = 0x15
PSKT_IN_TAP_BIP32_DERIVATION = 0x16
PSKT_IN_TAP_INTERNAL_KEY = 0x17
PSKT_IN_TAP_MERKLE_ROOT = 0x18
PSKT_IN_PROPRIETARY = 0xfc

# per-output types
PSKT_OUT_REDEEM_SCRIPT = 0x00
PSKT_OUT_WITNESS_SCRIPT = 0x01
PSKT_OUT_BIP32_DERIVATION = 0x02
PSKT_OUT_AMOUNT = 0x03
PSKT_OUT_SCRIPT = 0x04
PSKT_OUT_TAP_INTERNAL_KEY = 0x05
PSKT_OUT_TAP_TREE = 0x06
PSKT_OUT_TAP_BIP32_DERIVATION = 0x07
PSKT_OUT_PROPRIETARY = 0xfc


class PSKTMap:
    """Class for serializing and deserializing PSKT maps"""

    def __init__(self, map=None):
        self.map = map if map is not None else {}

    def deserialize(self, f):
        m = {}
        while True:
            k = deser_string(f)
            if len(k) == 0:
                break
            v = deser_string(f)
            if len(k) == 1:
                k = k[0]
            assert k not in m
            m[k] = v
        self.map = m

    def serialize(self):
        m = b""
        for k,v in self.map.items():
            if isinstance(k, int) and 0 <= k and k <= 255:
                k = bytes([k])
            m += ser_compact_size(len(k)) + k
            m += ser_compact_size(len(v)) + v
        m += b"\x00"
        return m

class PSKT:
    """Class for serializing and deserializing PSKTs"""

    def __init__(self, *, g=None, i=None, o=None):
        self.g = g if g is not None else PSKTMap()
        self.i = i if i is not None else []
        self.o = o if o is not None else []
        self.tx = None

    def deserialize(self, f):
        assert f.read(5) == b"pskt\xff"
        self.g = from_binary(PSKTMap, f)
        assert 0 in self.g.map
        self.tx = from_binary(CTransaction, self.g.map[0])
        self.i = [from_binary(PSKTMap, f) for _ in self.tx.vin]
        self.o = [from_binary(PSKTMap, f) for _ in self.tx.vout]
        return self

    def serialize(self):
        assert isinstance(self.g, PSKTMap)
        assert isinstance(self.i, list) and all(isinstance(x, PSKTMap) for x in self.i)
        assert isinstance(self.o, list) and all(isinstance(x, PSKTMap) for x in self.o)
        assert 0 in self.g.map
        tx = from_binary(CTransaction, self.g.map[0])
        assert len(tx.vin) == len(self.i)
        assert len(tx.vout) == len(self.o)

        pskt = [x.serialize() for x in [self.g] + self.i + self.o]
        return b"pskt\xff" + b"".join(pskt)

    def make_blank(self):
        """
        Remove all fields except for PSKT_GLOBAL_UNSIGNED_TX
        """
        for m in self.i + self.o:
            m.map.clear()

        self.g = PSKTMap(map={0: self.g.map[0]})

    def to_base64(self):
        return base64.b64encode(self.serialize()).decode("utf8")

    @classmethod
    def from_base64(cls, b64pskt):
        return from_binary(cls, base64.b64decode(b64pskt))
