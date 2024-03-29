#!/usr/bin/env python3
# Copyright (c) 2018-2021 The Bitcoin Core developers
# Copyright (c) 2023-2023 The Koyotecoin Core developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or http://www.opensource.org/licenses/mit-license.php.
"""Test the Partially Signed Transaction RPCs.
"""

from decimal import Decimal
from itertools import product

from test_framework.descriptors import descsum_create
from test_framework.key import ECKey, H_POINT
from test_framework.messages import (
    COutPoint,
    CTransaction,
    CTxIn,
    CTxOut,
    MAX_BIP125_RBF_SEQUENCE,
    WITNESS_SCALE_FACTOR,
    ser_compact_size,
)
from test_framework.pskt import (
    PSKT,
    PSKTMap,
    PSKT_GLOBAL_UNSIGNED_TX,
    PSKT_IN_RIPEMD160,
    PSKT_IN_SHA256,
    PSKT_IN_HASH160,
    PSKT_IN_HASH256,
    PSKT_OUT_TAP_TREE,
)
from test_framework.test_framework import KoyotecoinTestFramework
from test_framework.util import (
    assert_approx,
    assert_equal,
    assert_greater_than,
    assert_raises_rpc_error,
    find_output,
    find_vout_for_address,
    random_bytes,
)
from test_framework.wallet_util import bytes_to_wif

import json
import os


# Create one-input, one-output, no-fee transaction:
class PSKTTest(KoyotecoinTestFramework):

    def set_test_params(self):
        self.num_nodes = 3
        self.extra_args = [
            ["-walletrbf=1", "-addresstype=bech32", "-changetype=bech32"], #TODO: Remove address type restrictions once taproot has pskt extensions
            ["-walletrbf=0", "-changetype=legacy"],
            []
        ]
        self.supports_cli = False

    def skip_test_if_missing_module(self):
        self.skip_if_no_wallet()

    # TODO: Re-enable this test with segwit v1
    def test_utxo_conversion(self):
        mining_node = self.nodes[2]
        offline_node = self.nodes[0]
        online_node = self.nodes[1]

        # Disconnect offline node from others
        # Topology of test network is linear, so this one call is enough
        self.disconnect_nodes(0, 1)

        # Create watchonly on online_node
        online_node.createwallet(wallet_name='wonline', disable_private_keys=True)
        wonline = online_node.get_wallet_rpc('wonline')
        w2 = online_node.get_wallet_rpc('')

        # Mine a transaction that credits the offline address
        offline_addr = offline_node.getnewaddress(address_type="p2sh-segwit")
        online_addr = w2.getnewaddress(address_type="p2sh-segwit")
        wonline.importaddress(offline_addr, "", False)
        mining_node.sendtoaddress(address=offline_addr, amount=1.0)
        self.generate(mining_node, nblocks=1)

        # Construct an unsigned PSKT on the online node (who doesn't know the output is Segwit, so will include a non-witness UTXO)
        utxos = wonline.listunspent(addresses=[offline_addr])
        raw = wonline.createrawtransaction([{"txid":utxos[0]["txid"], "vout":utxos[0]["vout"]}],[{online_addr:0.9999}])
        pskt = wonline.walletprocesspskt(online_node.converttopskt(raw))["pskt"]
        assert "non_witness_utxo" in mining_node.decodepskt(pskt)["inputs"][0]

        # Have the offline node sign the PSKT (which will update the UTXO to segwit)
        signed_pskt = offline_node.walletprocesspskt(pskt)["pskt"]
        assert "witness_utxo" in mining_node.decodepskt(signed_pskt)["inputs"][0]

        # Make sure we can mine the resulting transaction
        txid = mining_node.sendrawtransaction(mining_node.finalizepskt(signed_pskt)["hex"])
        self.generate(mining_node, 1)
        assert_equal(online_node.gettxout(txid,0)["confirmations"], 1)

        wonline.unloadwallet()

        # Reconnect
        self.connect_nodes(0, 1)
        self.connect_nodes(0, 2)

    def assert_change_type(self, psktx, expected_type):
        """Assert that the given PSKT has a change output with the given type."""

        # The decodepskt RPC is stateless and independent of any settings, we can always just call it on the first node
        decoded_pskt = self.nodes[0].decodepskt(psktx["pskt"])
        changepos = psktx["changepos"]
        assert_equal(decoded_pskt["tx"]["vout"][changepos]["scriptPubKey"]["type"], expected_type)

    def run_test(self):
        # Create and fund a raw tx for sending 10 KYC
        psktx1 = self.nodes[0].walletcreatefundedpskt([], {self.nodes[2].getnewaddress():10})['pskt']

        # If inputs are specified, do not automatically add more:
        utxo1 = self.nodes[0].listunspent()[0]
        assert_raises_rpc_error(-4, "Insufficient funds", self.nodes[0].walletcreatefundedpskt, [{"txid": utxo1['txid'], "vout": utxo1['vout']}], {self.nodes[2].getnewaddress():90})

        psktx1 = self.nodes[0].walletcreatefundedpskt([{"txid": utxo1['txid'], "vout": utxo1['vout']}], {self.nodes[2].getnewaddress():90}, 0, {"add_inputs": True})['pskt']
        assert_equal(len(self.nodes[0].decodepskt(psktx1)['tx']['vin']), 2)

        # Inputs argument can be null
        self.nodes[0].walletcreatefundedpskt(None, {self.nodes[2].getnewaddress():10})

        # Node 1 should not be able to add anything to it but still return the psktx same as before
        psktx = self.nodes[1].walletprocesspskt(psktx1)['pskt']
        assert_equal(psktx1, psktx)

        # Node 0 should not be able to sign the transaction with the wallet is locked
        self.nodes[0].encryptwallet("password")
        assert_raises_rpc_error(-13, "Please enter the wallet passphrase with walletpassphrase first", self.nodes[0].walletprocesspskt, psktx)

        # Node 0 should be able to process without signing though
        unsigned_tx = self.nodes[0].walletprocesspskt(psktx, False)
        assert_equal(unsigned_tx['complete'], False)

        self.nodes[0].walletpassphrase(passphrase="password", timeout=1000000)

        # Sign the transaction and send
        signed_tx = self.nodes[0].walletprocesspskt(pskt=psktx, finalize=False)['pskt']
        finalized_tx = self.nodes[0].walletprocesspskt(pskt=psktx, finalize=True)['pskt']
        assert signed_tx != finalized_tx
        final_tx = self.nodes[0].finalizepskt(signed_tx)['hex']
        self.nodes[0].sendrawtransaction(final_tx)

        # Manually selected inputs can be locked:
        assert_equal(len(self.nodes[0].listlockunspent()), 0)
        utxo1 = self.nodes[0].listunspent()[0]
        psktx1 = self.nodes[0].walletcreatefundedpskt([{"txid": utxo1['txid'], "vout": utxo1['vout']}], {self.nodes[2].getnewaddress():1}, 0,{"lockUnspents": True})["pskt"]
        assert_equal(len(self.nodes[0].listlockunspent()), 1)

        # Locks are ignored for manually selected inputs
        self.nodes[0].walletcreatefundedpskt([{"txid": utxo1['txid'], "vout": utxo1['vout']}], {self.nodes[2].getnewaddress():1}, 0)

        # Create p2sh, p2wpkh, and p2wsh addresses
        pubkey0 = self.nodes[0].getaddressinfo(self.nodes[0].getnewaddress())['pubkey']
        pubkey1 = self.nodes[1].getaddressinfo(self.nodes[1].getnewaddress())['pubkey']
        pubkey2 = self.nodes[2].getaddressinfo(self.nodes[2].getnewaddress())['pubkey']

        # Setup watchonly wallets
        self.nodes[2].createwallet(wallet_name='wmulti', disable_private_keys=True)
        wmulti = self.nodes[2].get_wallet_rpc('wmulti')

        # Create all the addresses
        p2sh = wmulti.addmultisigaddress(2, [pubkey0, pubkey1, pubkey2], "", "legacy")['address']
        p2wsh = wmulti.addmultisigaddress(2, [pubkey0, pubkey1, pubkey2], "", "bech32")['address']
        p2sh_p2wsh = wmulti.addmultisigaddress(2, [pubkey0, pubkey1, pubkey2], "", "p2sh-segwit")['address']
        if not self.options.descriptors:
            wmulti.importaddress(p2sh)
            wmulti.importaddress(p2wsh)
            wmulti.importaddress(p2sh_p2wsh)
        p2wpkh = self.nodes[1].getnewaddress("", "bech32")
        p2pkh = self.nodes[1].getnewaddress("", "legacy")
        p2sh_p2wpkh = self.nodes[1].getnewaddress("", "p2sh-segwit")

        # fund those addresses
        rawtx = self.nodes[0].createrawtransaction([], {p2sh:10, p2wsh:10, p2wpkh:10, p2sh_p2wsh:10, p2sh_p2wpkh:10, p2pkh:10})
        rawtx = self.nodes[0].fundrawtransaction(rawtx, {"changePosition":3})
        signed_tx = self.nodes[0].signrawtransactionwithwallet(rawtx['hex'])['hex']
        txid = self.nodes[0].sendrawtransaction(signed_tx)
        self.generate(self.nodes[0], 6)

        # Find the output pos
        p2sh_pos = -1
        p2wsh_pos = -1
        p2wpkh_pos = -1
        p2pkh_pos = -1
        p2sh_p2wsh_pos = -1
        p2sh_p2wpkh_pos = -1
        decoded = self.nodes[0].decoderawtransaction(signed_tx)
        for out in decoded['vout']:
            if out['scriptPubKey']['address'] == p2sh:
                p2sh_pos = out['n']
            elif out['scriptPubKey']['address'] == p2wsh:
                p2wsh_pos = out['n']
            elif out['scriptPubKey']['address'] == p2wpkh:
                p2wpkh_pos = out['n']
            elif out['scriptPubKey']['address'] == p2sh_p2wsh:
                p2sh_p2wsh_pos = out['n']
            elif out['scriptPubKey']['address'] == p2sh_p2wpkh:
                p2sh_p2wpkh_pos = out['n']
            elif out['scriptPubKey']['address'] == p2pkh:
                p2pkh_pos = out['n']

        inputs = [{"txid": txid, "vout": p2wpkh_pos}, {"txid": txid, "vout": p2sh_p2wpkh_pos}, {"txid": txid, "vout": p2pkh_pos}]
        outputs = [{self.nodes[1].getnewaddress(): 29.99}]

        # spend single key from node 1
        created_pskt = self.nodes[1].walletcreatefundedpskt(inputs, outputs)
        walletprocesspskt_out = self.nodes[1].walletprocesspskt(created_pskt['pskt'])
        # Make sure it has both types of UTXOs
        decoded = self.nodes[1].decodepskt(walletprocesspskt_out['pskt'])
        assert 'non_witness_utxo' in decoded['inputs'][0]
        assert 'witness_utxo' in decoded['inputs'][0]
        # Check decodepskt fee calculation (input values shall only be counted once per UTXO)
        assert_equal(decoded['fee'], created_pskt['fee'])
        assert_equal(walletprocesspskt_out['complete'], True)
        self.nodes[1].sendrawtransaction(self.nodes[1].finalizepskt(walletprocesspskt_out['pskt'])['hex'])

        self.log.info("Test walletcreatefundedpskt fee rate of 10000 howl/vB and 0.1 KYC/kvB produces a total fee at or slightly below -maxtxfee (~0.05290000)")
        res1 = self.nodes[1].walletcreatefundedpskt(inputs, outputs, 0, {"fee_rate": 10000, "add_inputs": True})
        assert_approx(res1["fee"], 0.055, 0.005)
        res2 = self.nodes[1].walletcreatefundedpskt(inputs, outputs, 0, {"feeRate": "0.1", "add_inputs": True})
        assert_approx(res2["fee"], 0.055, 0.005)

        self.log.info("Test min fee rate checks with walletcreatefundedpskt are bypassed, e.g. a fee_rate under 1 howl/vB is allowed")
        res3 = self.nodes[1].walletcreatefundedpskt(inputs, outputs, 0, {"fee_rate": "0.999", "add_inputs": True})
        assert_approx(res3["fee"], 0.00000381, 0.0000001)
        res4 = self.nodes[1].walletcreatefundedpskt(inputs, outputs, 0, {"feeRate": 0.00000999, "add_inputs": True})
        assert_approx(res4["fee"], 0.00000381, 0.0000001)

        self.log.info("Test min fee rate checks with walletcreatefundedpskt are bypassed and that funding non-standard 'zero-fee' transactions is valid")
        for param, zero_value in product(["fee_rate", "feeRate"], [0, 0.000, 0.00000000, "0", "0.000", "0.00000000"]):
            assert_equal(0, self.nodes[1].walletcreatefundedpskt(inputs, outputs, 0, {param: zero_value, "add_inputs": True})["fee"])

        self.log.info("Test invalid fee rate settings")
        for param, value in {("fee_rate", 100000), ("feeRate", 1)}:
            assert_raises_rpc_error(-4, "Fee exceeds maximum configured by user (e.g. -maxtxfee, maxfeerate)",
                self.nodes[1].walletcreatefundedpskt, inputs, outputs, 0, {param: value, "add_inputs": True})
            assert_raises_rpc_error(-3, "Amount out of range",
                self.nodes[1].walletcreatefundedpskt, inputs, outputs, 0, {param: -1, "add_inputs": True})
            assert_raises_rpc_error(-3, "Amount is not a number or string",
                self.nodes[1].walletcreatefundedpskt, inputs, outputs, 0, {param: {"foo": "bar"}, "add_inputs": True})
            # Test fee rate values that don't pass fixed-point parsing checks.
            for invalid_value in ["", 0.000000001, 1e-09, 1.111111111, 1111111111111111, "31.999999999999999999999"]:
                assert_raises_rpc_error(-3, "Invalid amount",
                    self.nodes[1].walletcreatefundedpskt, inputs, outputs, 0, {param: invalid_value, "add_inputs": True})
        # Test fee_rate values that cannot be represented in howl/vB.
        for invalid_value in [0.0001, 0.00000001, 0.00099999, 31.99999999, "0.0001", "0.00000001", "0.00099999", "31.99999999"]:
            assert_raises_rpc_error(-3, "Invalid amount",
                self.nodes[1].walletcreatefundedpskt, inputs, outputs, 0, {"fee_rate": invalid_value, "add_inputs": True})

        self.log.info("- raises RPC error if both feeRate and fee_rate are passed")
        assert_raises_rpc_error(-8, "Cannot specify both fee_rate (howl/vB) and feeRate (KYC/kvB)",
            self.nodes[1].walletcreatefundedpskt, inputs, outputs, 0, {"fee_rate": 0.1, "feeRate": 0.1, "add_inputs": True})

        self.log.info("- raises RPC error if both feeRate and estimate_mode passed")
        assert_raises_rpc_error(-8, "Cannot specify both estimate_mode and feeRate",
            self.nodes[1].walletcreatefundedpskt, inputs, outputs, 0, {"estimate_mode": "economical", "feeRate": 0.1, "add_inputs": True})

        for param in ["feeRate", "fee_rate"]:
            self.log.info("- raises RPC error if both {} and conf_target are passed".format(param))
            assert_raises_rpc_error(-8, "Cannot specify both conf_target and {}. Please provide either a confirmation "
                "target in blocks for automatic fee estimation, or an explicit fee rate.".format(param),
                self.nodes[1].walletcreatefundedpskt ,inputs, outputs, 0, {param: 1, "conf_target": 1, "add_inputs": True})

        self.log.info("- raises RPC error if both fee_rate and estimate_mode are passed")
        assert_raises_rpc_error(-8, "Cannot specify both estimate_mode and fee_rate",
            self.nodes[1].walletcreatefundedpskt ,inputs, outputs, 0, {"fee_rate": 1, "estimate_mode": "economical", "add_inputs": True})

        self.log.info("- raises RPC error with invalid estimate_mode settings")
        for k, v in {"number": 42, "object": {"foo": "bar"}}.items():
            assert_raises_rpc_error(-3, "Expected type string for estimate_mode, got {}".format(k),
                self.nodes[1].walletcreatefundedpskt, inputs, outputs, 0, {"estimate_mode": v, "conf_target": 0.1, "add_inputs": True})
        for mode in ["", "foo", Decimal("3.141592")]:
            assert_raises_rpc_error(-8, 'Invalid estimate_mode parameter, must be one of: "unset", "economical", "conservative"',
                self.nodes[1].walletcreatefundedpskt, inputs, outputs, 0, {"estimate_mode": mode, "conf_target": 0.1, "add_inputs": True})

        self.log.info("- raises RPC error with invalid conf_target settings")
        for mode in ["unset", "economical", "conservative"]:
            self.log.debug("{}".format(mode))
            for k, v in {"string": "", "object": {"foo": "bar"}}.items():
                assert_raises_rpc_error(-3, "Expected type number for conf_target, got {}".format(k),
                    self.nodes[1].walletcreatefundedpskt, inputs, outputs, 0, {"estimate_mode": mode, "conf_target": v, "add_inputs": True})
            for n in [-1, 0, 1009]:
                assert_raises_rpc_error(-8, "Invalid conf_target, must be between 1 and 1008",  # max value of 1008 per src/policy/fees.h
                    self.nodes[1].walletcreatefundedpskt, inputs, outputs, 0, {"estimate_mode": mode, "conf_target": n, "add_inputs": True})

        self.log.info("Test walletcreatefundedpskt with too-high fee rate produces total fee well above -maxtxfee and raises RPC error")
        # previously this was silently capped at -maxtxfee
        for bool_add, outputs_array in {True: outputs, False: [{self.nodes[1].getnewaddress(): 1}]}.items():
            msg = "Fee exceeds maximum configured by user (e.g. -maxtxfee, maxfeerate)"
            assert_raises_rpc_error(-4, msg, self.nodes[1].walletcreatefundedpskt, inputs, outputs_array, 0, {"fee_rate": 1000000, "add_inputs": bool_add})
            assert_raises_rpc_error(-4, msg, self.nodes[1].walletcreatefundedpskt, inputs, outputs_array, 0, {"feeRate": 1, "add_inputs": bool_add})

        self.log.info("Test various PSKT operations")
        # partially sign multisig things with node 1
        psktx = wmulti.walletcreatefundedpskt(inputs=[{"txid":txid,"vout":p2wsh_pos},{"txid":txid,"vout":p2sh_pos},{"txid":txid,"vout":p2sh_p2wsh_pos}], outputs={self.nodes[1].getnewaddress():29.99}, options={'changeAddress': self.nodes[1].getrawchangeaddress()})['pskt']
        walletprocesspskt_out = self.nodes[1].walletprocesspskt(psktx)
        psktx = walletprocesspskt_out['pskt']
        assert_equal(walletprocesspskt_out['complete'], False)

        # Unload wmulti, we don't need it anymore
        wmulti.unloadwallet()

        # partially sign with node 2. This should be complete and sendable
        walletprocesspskt_out = self.nodes[2].walletprocesspskt(psktx)
        assert_equal(walletprocesspskt_out['complete'], True)
        self.nodes[2].sendrawtransaction(self.nodes[2].finalizepskt(walletprocesspskt_out['pskt'])['hex'])

        # check that walletprocesspskt fails to decode a non-pskt
        rawtx = self.nodes[1].createrawtransaction([{"txid":txid,"vout":p2wpkh_pos}], {self.nodes[1].getnewaddress():9.99})
        assert_raises_rpc_error(-22, "TX decode failed", self.nodes[1].walletprocesspskt, rawtx)

        # Convert a non-pskt to pskt and make sure we can decode it
        rawtx = self.nodes[0].createrawtransaction([], {self.nodes[1].getnewaddress():10})
        rawtx = self.nodes[0].fundrawtransaction(rawtx)
        new_pskt = self.nodes[0].converttopskt(rawtx['hex'])
        self.nodes[0].decodepskt(new_pskt)

        # Make sure that a non-pskt with signatures cannot be converted
        # Error could be either "TX decode failed" (segwit inputs causes parsing to fail) or "Inputs must not have scriptSigs and scriptWitnesses"
        # We must set iswitness=True because the serialized transaction has inputs and is therefore a witness transaction
        signedtx = self.nodes[0].signrawtransactionwithwallet(rawtx['hex'])
        assert_raises_rpc_error(-22, "", self.nodes[0].converttopskt, hexstring=signedtx['hex'], iswitness=True)
        assert_raises_rpc_error(-22, "", self.nodes[0].converttopskt, hexstring=signedtx['hex'], permitsigdata=False, iswitness=True)
        # Unless we allow it to convert and strip signatures
        self.nodes[0].converttopskt(signedtx['hex'], True)

        # Explicitly allow converting non-empty txs
        new_pskt = self.nodes[0].converttopskt(rawtx['hex'])
        self.nodes[0].decodepskt(new_pskt)

        # Create outputs to nodes 1 and 2
        node1_addr = self.nodes[1].getnewaddress()
        node2_addr = self.nodes[2].getnewaddress()
        txid1 = self.nodes[0].sendtoaddress(node1_addr, 13)
        txid2 = self.nodes[0].sendtoaddress(node2_addr, 13)
        blockhash = self.generate(self.nodes[0], 6)[0]
        vout1 = find_output(self.nodes[1], txid1, 13, blockhash=blockhash)
        vout2 = find_output(self.nodes[2], txid2, 13, blockhash=blockhash)

        # Create a pskt spending outputs from nodes 1 and 2
        pskt_orig = self.nodes[0].createpskt([{"txid":txid1,  "vout":vout1}, {"txid":txid2, "vout":vout2}], {self.nodes[0].getnewaddress():25.999})

        # Update pskts, should only have data for one input and not the other
        pskt1 = self.nodes[1].walletprocesspskt(pskt_orig, False, "ALL")['pskt']
        pskt1_decoded = self.nodes[0].decodepskt(pskt1)
        assert pskt1_decoded['inputs'][0] and not pskt1_decoded['inputs'][1]
        # Check that BIP32 path was added
        assert "bip32_derivs" in pskt1_decoded['inputs'][0]
        pskt2 = self.nodes[2].walletprocesspskt(pskt_orig, False, "ALL", False)['pskt']
        pskt2_decoded = self.nodes[0].decodepskt(pskt2)
        assert not pskt2_decoded['inputs'][0] and pskt2_decoded['inputs'][1]
        # Check that BIP32 paths were not added
        assert "bip32_derivs" not in pskt2_decoded['inputs'][1]

        # Sign PSKTs (workaround issue #18039)
        pskt1 = self.nodes[1].walletprocesspskt(pskt_orig)['pskt']
        pskt2 = self.nodes[2].walletprocesspskt(pskt_orig)['pskt']

        # Combine, finalize, and send the pskts
        combined = self.nodes[0].combinepskt([pskt1, pskt2])
        finalized = self.nodes[0].finalizepskt(combined)['hex']
        self.nodes[0].sendrawtransaction(finalized)
        self.generate(self.nodes[0], 6)

        # Test additional args in walletcreatepskt
        # Make sure both pre-included and funded inputs
        # have the correct sequence numbers based on
        # replaceable arg
        block_height = self.nodes[0].getblockcount()
        unspent = self.nodes[0].listunspent()[0]
        psktx_info = self.nodes[0].walletcreatefundedpskt([{"txid":unspent["txid"], "vout":unspent["vout"]}], [{self.nodes[2].getnewaddress():unspent["amount"]+1}], block_height+2, {"replaceable": False, "add_inputs": True}, False)
        decoded_pskt = self.nodes[0].decodepskt(psktx_info["pskt"])
        for tx_in, pskt_in in zip(decoded_pskt["tx"]["vin"], decoded_pskt["inputs"]):
            assert_greater_than(tx_in["sequence"], MAX_BIP125_RBF_SEQUENCE)
            assert "bip32_derivs" not in pskt_in
        assert_equal(decoded_pskt["tx"]["locktime"], block_height+2)

        # Same construction with only locktime set and RBF explicitly enabled
        psktx_info = self.nodes[0].walletcreatefundedpskt([{"txid":unspent["txid"], "vout":unspent["vout"]}], [{self.nodes[2].getnewaddress():unspent["amount"]+1}], block_height, {"replaceable": True, "add_inputs": True}, True)
        decoded_pskt = self.nodes[0].decodepskt(psktx_info["pskt"])
        for tx_in, pskt_in in zip(decoded_pskt["tx"]["vin"], decoded_pskt["inputs"]):
            assert_equal(tx_in["sequence"], MAX_BIP125_RBF_SEQUENCE)
            assert "bip32_derivs" in pskt_in
        assert_equal(decoded_pskt["tx"]["locktime"], block_height)

        # Same construction without optional arguments
        psktx_info = self.nodes[0].walletcreatefundedpskt([], [{self.nodes[2].getnewaddress():unspent["amount"]+1}])
        decoded_pskt = self.nodes[0].decodepskt(psktx_info["pskt"])
        for tx_in, pskt_in in zip(decoded_pskt["tx"]["vin"], decoded_pskt["inputs"]):
            assert_equal(tx_in["sequence"], MAX_BIP125_RBF_SEQUENCE)
            assert "bip32_derivs" in pskt_in
        assert_equal(decoded_pskt["tx"]["locktime"], 0)

        # Same construction without optional arguments, for a node with -walletrbf=0
        unspent1 = self.nodes[1].listunspent()[0]
        psktx_info = self.nodes[1].walletcreatefundedpskt([{"txid":unspent1["txid"], "vout":unspent1["vout"]}], [{self.nodes[2].getnewaddress():unspent1["amount"]+1}], block_height, {"add_inputs": True})
        decoded_pskt = self.nodes[1].decodepskt(psktx_info["pskt"])
        for tx_in, pskt_in in zip(decoded_pskt["tx"]["vin"], decoded_pskt["inputs"]):
            assert_greater_than(tx_in["sequence"], MAX_BIP125_RBF_SEQUENCE)
            assert "bip32_derivs" in pskt_in

        # Make sure change address wallet does not have P2SH innerscript access to results in success
        # when attempting BnB coin selection
        self.nodes[0].walletcreatefundedpskt([], [{self.nodes[2].getnewaddress():unspent["amount"]+1}], block_height+2, {"changeAddress":self.nodes[1].getnewaddress()}, False)

        # Make sure the wallet's change type is respected by default
        small_output = {self.nodes[0].getnewaddress():0.1}
        psktx_native = self.nodes[0].walletcreatefundedpskt([], [small_output])
        self.assert_change_type(psktx_native, "witness_v0_keyhash")
        psktx_legacy = self.nodes[1].walletcreatefundedpskt([], [small_output])
        self.assert_change_type(psktx_legacy, "pubkeyhash")

        # Make sure the change type of the wallet can also be overwritten
        psktx_np2wkh = self.nodes[1].walletcreatefundedpskt([], [small_output], 0, {"change_type":"p2sh-segwit"})
        self.assert_change_type(psktx_np2wkh, "scripthash")

        # Make sure the change type cannot be specified if a change address is given
        invalid_options = {"change_type":"legacy","changeAddress":self.nodes[0].getnewaddress()}
        assert_raises_rpc_error(-8, "both change address and address type options", self.nodes[0].walletcreatefundedpskt, [], [small_output], 0, invalid_options)

        # Regression test for 14473 (mishandling of already-signed witness transaction):
        psktx_info = self.nodes[0].walletcreatefundedpskt([{"txid":unspent["txid"], "vout":unspent["vout"]}], [{self.nodes[2].getnewaddress():unspent["amount"]+1}], 0, {"add_inputs": True})
        complete_pskt = self.nodes[0].walletprocesspskt(psktx_info["pskt"])
        double_processed_pskt = self.nodes[0].walletprocesspskt(complete_pskt["pskt"])
        assert_equal(complete_pskt, double_processed_pskt)
        # We don't care about the decode result, but decoding must succeed.
        self.nodes[0].decodepskt(double_processed_pskt["pskt"])

        # Make sure unsafe inputs are included if specified
        self.nodes[2].createwallet(wallet_name="unsafe")
        wunsafe = self.nodes[2].get_wallet_rpc("unsafe")
        self.nodes[0].sendtoaddress(wunsafe.getnewaddress(), 2)
        self.sync_mempools()
        assert_raises_rpc_error(-4, "Insufficient funds", wunsafe.walletcreatefundedpskt, [], [{self.nodes[0].getnewaddress(): 1}])
        wunsafe.walletcreatefundedpskt([], [{self.nodes[0].getnewaddress(): 1}], 0, {"include_unsafe": True})

        # BIP 174 Test Vectors

        # Check that unknown values are just passed through
        unknown_pskt = "cHNidP8BAD8CAAAAAf//////////////////////////////////////////AAAAAAD/////AQAAAAAAAAAAA2oBAAAAAAAACg8BAgMEBQYHCAkPAQIDBAUGBwgJCgsMDQ4PAAA="
        unknown_out = self.nodes[0].walletprocesspskt(unknown_pskt)['pskt']
        assert_equal(unknown_pskt, unknown_out)

        # Open the data file
        with open(os.path.join(os.path.dirname(os.path.realpath(__file__)), 'data/rpc_pskt.json'), encoding='utf-8') as f:
            d = json.load(f)
            invalids = d['invalid']
            invalid_with_msgs = d["invalid_with_msg"]
            valids = d['valid']
            creators = d['creator']
            signers = d['signer']
            combiners = d['combiner']
            finalizers = d['finalizer']
            extractors = d['extractor']

        # Invalid PSKTs
        for invalid in invalids:
            assert_raises_rpc_error(-22, "TX decode failed", self.nodes[0].decodepskt, invalid)
        for invalid in invalid_with_msgs:
            pskt, msg = invalid
            assert_raises_rpc_error(-22, f"TX decode failed {msg}", self.nodes[0].decodepskt, pskt)

        # Valid PSKTs
        for valid in valids:
            self.nodes[0].decodepskt(valid)

        # Creator Tests
        for creator in creators:
            created_tx = self.nodes[0].createpskt(inputs=creator['inputs'], outputs=creator['outputs'], replaceable=False)
            assert_equal(created_tx, creator['result'])

        # Signer tests
        for i, signer in enumerate(signers):
            self.nodes[2].createwallet(wallet_name="wallet{}".format(i))
            wrpc = self.nodes[2].get_wallet_rpc("wallet{}".format(i))
            for key in signer['privkeys']:
                wrpc.importprivkey(key)
            signed_tx = wrpc.walletprocesspskt(signer['pskt'], True, "ALL")['pskt']
            assert_equal(signed_tx, signer['result'])

        # Combiner test
        for combiner in combiners:
            combined = self.nodes[2].combinepskt(combiner['combine'])
            assert_equal(combined, combiner['result'])

        # Empty combiner test
        assert_raises_rpc_error(-8, "Parameter 'txs' cannot be empty", self.nodes[0].combinepskt, [])

        # Finalizer test
        for finalizer in finalizers:
            finalized = self.nodes[2].finalizepskt(finalizer['finalize'], False)['pskt']
            assert_equal(finalized, finalizer['result'])

        # Extractor test
        for extractor in extractors:
            extracted = self.nodes[2].finalizepskt(extractor['extract'], True)['hex']
            assert_equal(extracted, extractor['result'])

        # Unload extra wallets
        for i, signer in enumerate(signers):
            self.nodes[2].unloadwallet("wallet{}".format(i))

        # TODO: Re-enable this for segwit v1
        # self.test_utxo_conversion()

        # Test that pskts with p2pkh outputs are created properly
        p2pkh = self.nodes[0].getnewaddress(address_type='legacy')
        pskt = self.nodes[1].walletcreatefundedpskt([], [{p2pkh : 1}], 0, {"includeWatching" : True}, True)
        self.nodes[0].decodepskt(pskt['pskt'])

        # Test decoding error: invalid base64
        assert_raises_rpc_error(-22, "TX decode failed invalid base64", self.nodes[0].decodepskt, ";definitely not base64;")

        # Send to all types of addresses
        addr1 = self.nodes[1].getnewaddress("", "bech32")
        txid1 = self.nodes[0].sendtoaddress(addr1, 11)
        vout1 = find_output(self.nodes[0], txid1, 11)
        addr2 = self.nodes[1].getnewaddress("", "legacy")
        txid2 = self.nodes[0].sendtoaddress(addr2, 11)
        vout2 = find_output(self.nodes[0], txid2, 11)
        addr3 = self.nodes[1].getnewaddress("", "p2sh-segwit")
        txid3 = self.nodes[0].sendtoaddress(addr3, 11)
        vout3 = find_output(self.nodes[0], txid3, 11)
        self.sync_all()

        def test_pskt_input_keys(pskt_input, keys):
            """Check that the pskt input has only the expected keys."""
            assert_equal(set(keys), set(pskt_input.keys()))

        # Create a PSKT. None of the inputs are filled initially
        pskt = self.nodes[1].createpskt([{"txid":txid1, "vout":vout1},{"txid":txid2, "vout":vout2},{"txid":txid3, "vout":vout3}], {self.nodes[0].getnewaddress():32.999})
        decoded = self.nodes[1].decodepskt(pskt)
        test_pskt_input_keys(decoded['inputs'][0], [])
        test_pskt_input_keys(decoded['inputs'][1], [])
        test_pskt_input_keys(decoded['inputs'][2], [])

        # Update a PSKT with UTXOs from the node
        # Bech32 inputs should be filled with witness UTXO. Other inputs should not be filled because they are non-witness
        updated = self.nodes[1].utxoupdatepskt(pskt)
        decoded = self.nodes[1].decodepskt(updated)
        test_pskt_input_keys(decoded['inputs'][0], ['witness_utxo'])
        test_pskt_input_keys(decoded['inputs'][1], [])
        test_pskt_input_keys(decoded['inputs'][2], [])

        # Try again, now while providing descriptors, making P2SH-segwit work, and causing bip32_derivs and redeem_script to be filled in
        descs = [self.nodes[1].getaddressinfo(addr)['desc'] for addr in [addr1,addr2,addr3]]
        updated = self.nodes[1].utxoupdatepskt(pskt=pskt, descriptors=descs)
        decoded = self.nodes[1].decodepskt(updated)
        test_pskt_input_keys(decoded['inputs'][0], ['witness_utxo', 'bip32_derivs'])
        test_pskt_input_keys(decoded['inputs'][1], [])
        test_pskt_input_keys(decoded['inputs'][2], ['witness_utxo', 'bip32_derivs', 'redeem_script'])

        # Two PSKTs with a common input should not be joinable
        pskt1 = self.nodes[1].createpskt([{"txid":txid1, "vout":vout1}], {self.nodes[0].getnewaddress():Decimal('10.999')})
        assert_raises_rpc_error(-8, "exists in multiple PSKTs", self.nodes[1].joinpskts, [pskt1, updated])

        # Join two distinct PSKTs
        addr4 = self.nodes[1].getnewaddress("", "p2sh-segwit")
        txid4 = self.nodes[0].sendtoaddress(addr4, 5)
        vout4 = find_output(self.nodes[0], txid4, 5)
        self.generate(self.nodes[0], 6)
        pskt2 = self.nodes[1].createpskt([{"txid":txid4, "vout":vout4}], {self.nodes[0].getnewaddress():Decimal('4.999')})
        pskt2 = self.nodes[1].walletprocesspskt(pskt2)['pskt']
        pskt2_decoded = self.nodes[0].decodepskt(pskt2)
        assert "final_scriptwitness" in pskt2_decoded['inputs'][0] and "final_scriptSig" in pskt2_decoded['inputs'][0]
        joined = self.nodes[0].joinpskts([pskt, pskt2])
        joined_decoded = self.nodes[0].decodepskt(joined)
        assert len(joined_decoded['inputs']) == 4 and len(joined_decoded['outputs']) == 2 and "final_scriptwitness" not in joined_decoded['inputs'][3] and "final_scriptSig" not in joined_decoded['inputs'][3]

        # Check that joining shuffles the inputs and outputs
        # 10 attempts should be enough to get a shuffled join
        shuffled = False
        for _ in range(10):
            shuffled_joined = self.nodes[0].joinpskts([pskt, pskt2])
            shuffled |= joined != shuffled_joined
            if shuffled:
                break
        assert shuffled

        # Newly created PSKT needs UTXOs and updating
        addr = self.nodes[1].getnewaddress("", "p2sh-segwit")
        txid = self.nodes[0].sendtoaddress(addr, 7)
        addrinfo = self.nodes[1].getaddressinfo(addr)
        blockhash = self.generate(self.nodes[0], 6)[0]
        vout = find_output(self.nodes[0], txid, 7, blockhash=blockhash)
        pskt = self.nodes[1].createpskt([{"txid":txid, "vout":vout}], {self.nodes[0].getnewaddress("", "p2sh-segwit"):Decimal('6.999')})
        analyzed = self.nodes[0].analyzepskt(pskt)
        assert not analyzed['inputs'][0]['has_utxo'] and not analyzed['inputs'][0]['is_final'] and analyzed['inputs'][0]['next'] == 'updater' and analyzed['next'] == 'updater'

        # After update with wallet, only needs signing
        updated = self.nodes[1].walletprocesspskt(pskt, False, 'ALL', True)['pskt']
        analyzed = self.nodes[0].analyzepskt(updated)
        assert analyzed['inputs'][0]['has_utxo'] and not analyzed['inputs'][0]['is_final'] and analyzed['inputs'][0]['next'] == 'signer' and analyzed['next'] == 'signer' and analyzed['inputs'][0]['missing']['signatures'][0] == addrinfo['embedded']['witness_program']

        # Check fee and size things
        assert analyzed['fee'] == Decimal('0.001') and analyzed['estimated_vsize'] == 134 and analyzed['estimated_feerate'] == Decimal('0.00746268')

        # After signing and finalizing, needs extracting
        signed = self.nodes[1].walletprocesspskt(updated)['pskt']
        analyzed = self.nodes[0].analyzepskt(signed)
        assert analyzed['inputs'][0]['has_utxo'] and analyzed['inputs'][0]['is_final'] and analyzed['next'] == 'extractor'

        self.log.info("PSKT spending unspendable outputs should have error message and Creator as next")
        analysis = self.nodes[0].analyzepskt('cHNidP8BAJoCAAAAAljoeiG1ba8MI76OcHBFbDNvfLqlyHV5JPVFiHuyq911AAAAAAD/////g40EJ9DsZQpoqka7CwmK6kQiwHGyyng1Kgd5WdB86h0BAAAAAP////8CcKrwCAAAAAAWAEHYXCtx0AYLCcmIauuBXlCZHdoSTQDh9QUAAAAAFv8/wADXYP/7//////8JxOh0LR2HAI8AAAAAAAEBIADC6wsAAAAAF2oUt/X69ELjeX2nTof+fZ10l+OyAokDAQcJAwEHEAABAACAAAEBIADC6wsAAAAAF2oUt/X69ELjeX2nTof+fZ10l+OyAokDAQcJAwEHENkMak8AAAAA')
        assert_equal(analysis['next'], 'creator')
        assert_equal(analysis['error'], 'PSKT is not valid. Input 0 spends unspendable output')

        self.log.info("PSKT with invalid values should have error message and Creator as next")
        analysis = self.nodes[0].analyzepskt('cHNidP8BAHECAAAAAfA00BFgAm6tp86RowwH6BMImQNL5zXUcTT97XoLGz0BAAAAAAD/////AgD5ApUAAAAAFgAUKNw0x8HRctAgmvoevm4u1SbN7XL87QKVAAAAABYAFPck4gF7iL4NL4wtfRAKgQbghiTUAAAAAAABAR8AgIFq49AHABYAFJUDtxf2PHo641HEOBOAIvFMNTr2AAAA')
        assert_equal(analysis['next'], 'creator')
        assert_equal(analysis['error'], 'PSKT is not valid. Input 0 has invalid value')

        self.log.info("PSKT with signed, but not finalized, inputs should have Finalizer as next")
        analysis = self.nodes[0].analyzepskt('cHNidP8BAHECAAAAAZYezcxdnbXoQCmrD79t/LzDgtUo9ERqixk8wgioAobrAAAAAAD9////AlDDAAAAAAAAFgAUy/UxxZuzZswcmFnN/E9DGSiHLUsuGPUFAAAAABYAFLsH5o0R38wXx+X2cCosTMCZnQ4baAAAAAABAR8A4fUFAAAAABYAFOBI2h5thf3+Lflb2LGCsVSZwsltIgIC/i4dtVARCRWtROG0HHoGcaVklzJUcwo5homgGkSNAnJHMEQCIGx7zKcMIGr7cEES9BR4Kdt/pzPTK3fKWcGyCJXb7MVnAiALOBgqlMH4GbC1HDh/HmylmO54fyEy4lKde7/BT/PWxwEBAwQBAAAAIgYC/i4dtVARCRWtROG0HHoGcaVklzJUcwo5homgGkSNAnIYDwVpQ1QAAIABAACAAAAAgAAAAAAAAAAAAAAiAgL+CIiB59NSCssOJRGiMYQK1chahgAaaJpIXE41Cyir+xgPBWlDVAAAgAEAAIAAAACAAQAAAAAAAAAA')
        assert_equal(analysis['next'], 'finalizer')

        analysis = self.nodes[0].analyzepskt('cHNidP8BAHECAAAAAfA00BFgAm6tp86RowwH6BMImQNL5zXUcTT97XoLGz0BAAAAAAD/////AgCAgWrj0AcAFgAUKNw0x8HRctAgmvoevm4u1SbN7XL87QKVAAAAABYAFPck4gF7iL4NL4wtfRAKgQbghiTUAAAAAAABAR8A8gUqAQAAABYAFJUDtxf2PHo641HEOBOAIvFMNTr2AAAA')
        assert_equal(analysis['next'], 'creator')
        assert_equal(analysis['error'], 'PSKT is not valid. Output amount invalid')

        analysis = self.nodes[0].analyzepskt('cHNidP8BAJoCAAAAAkvEW8NnDtdNtDpsmze+Ht2LH35IJcKv00jKAlUs21RrAwAAAAD/////S8Rbw2cO1020OmybN74e3Ysffkglwq/TSMoCVSzbVGsBAAAAAP7///8CwLYClQAAAAAWABSNJKzjaUb3uOxixsvh1GGE3fW7zQD5ApUAAAAAFgAUKNw0x8HRctAgmvoevm4u1SbN7XIAAAAAAAEAnQIAAAACczMa321tVHuN4GKWKRncycI22aX3uXgwSFUKM2orjRsBAAAAAP7///9zMxrfbW1Ue43gYpYpGdzJwjbZpfe5eDBIVQozaiuNGwAAAAAA/v///wIA+QKVAAAAABl2qRT9zXUVA8Ls5iVqynLHe5/vSe1XyYisQM0ClQAAAAAWABRmWQUcjSjghQ8/uH4Bn/zkakwLtAAAAAAAAQEfQM0ClQAAAAAWABRmWQUcjSjghQ8/uH4Bn/zkakwLtAAAAA==')
        assert_equal(analysis['next'], 'creator')
        assert_equal(analysis['error'], 'PSKT is not valid. Input 0 specifies invalid prevout')

        assert_raises_rpc_error(-25, 'Inputs missing or spent', self.nodes[0].walletprocesspskt, 'cHNidP8BAJoCAAAAAkvEW8NnDtdNtDpsmze+Ht2LH35IJcKv00jKAlUs21RrAwAAAAD/////S8Rbw2cO1020OmybN74e3Ysffkglwq/TSMoCVSzbVGsBAAAAAP7///8CwLYClQAAAAAWABSNJKzjaUb3uOxixsvh1GGE3fW7zQD5ApUAAAAAFgAUKNw0x8HRctAgmvoevm4u1SbN7XIAAAAAAAEAnQIAAAACczMa321tVHuN4GKWKRncycI22aX3uXgwSFUKM2orjRsBAAAAAP7///9zMxrfbW1Ue43gYpYpGdzJwjbZpfe5eDBIVQozaiuNGwAAAAAA/v///wIA+QKVAAAAABl2qRT9zXUVA8Ls5iVqynLHe5/vSe1XyYisQM0ClQAAAAAWABRmWQUcjSjghQ8/uH4Bn/zkakwLtAAAAAAAAQEfQM0ClQAAAAAWABRmWQUcjSjghQ8/uH4Bn/zkakwLtAAAAA==')

        self.log.info("Test that we can fund pskts with external inputs specified")

        eckey = ECKey()
        eckey.generate()
        privkey = bytes_to_wif(eckey.get_bytes())

        self.nodes[1].createwallet("extfund")
        wallet = self.nodes[1].get_wallet_rpc("extfund")

        # Make a weird but signable script. sh(wsh(pkh())) descriptor accomplishes this
        desc = descsum_create("sh(wsh(pkh({})))".format(privkey))
        if self.options.descriptors:
            res = self.nodes[0].importdescriptors([{"desc": desc, "timestamp": "now"}])
        else:
            res = self.nodes[0].importmulti([{"desc": desc, "timestamp": "now"}])
        assert res[0]["success"]
        addr = self.nodes[0].deriveaddresses(desc)[0]
        addr_info = self.nodes[0].getaddressinfo(addr)

        self.nodes[0].sendtoaddress(addr, 10)
        self.nodes[0].sendtoaddress(wallet.getnewaddress(), 10)
        self.generate(self.nodes[0], 6)
        ext_utxo = self.nodes[0].listunspent(addresses=[addr])[0]

        # An external input without solving data should result in an error
        assert_raises_rpc_error(-4, "Insufficient funds", wallet.walletcreatefundedpskt, [ext_utxo], {self.nodes[0].getnewaddress(): 15})

        # But funding should work when the solving data is provided
        pskt = wallet.walletcreatefundedpskt([ext_utxo], {self.nodes[0].getnewaddress(): 15}, 0, {"add_inputs": True, "solving_data": {"pubkeys": [addr_info['pubkey']], "scripts": [addr_info["embedded"]["scriptPubKey"], addr_info["embedded"]["embedded"]["scriptPubKey"]]}})
        signed = wallet.walletprocesspskt(pskt['pskt'])
        assert not signed['complete']
        signed = self.nodes[0].walletprocesspskt(signed['pskt'])
        assert signed['complete']
        self.nodes[0].finalizepskt(signed['pskt'])

        pskt = wallet.walletcreatefundedpskt([ext_utxo], {self.nodes[0].getnewaddress(): 15}, 0, {"add_inputs": True, "solving_data":{"descriptors": [desc]}})
        signed = wallet.walletprocesspskt(pskt['pskt'])
        assert not signed['complete']
        signed = self.nodes[0].walletprocesspskt(signed['pskt'])
        assert signed['complete']
        final = self.nodes[0].finalizepskt(signed['pskt'], False)

        dec = self.nodes[0].decodepskt(signed["pskt"])
        for i, txin in enumerate(dec["tx"]["vin"]):
            if txin["txid"] == ext_utxo["txid"] and txin["vout"] == ext_utxo["vout"]:
                input_idx = i
                break
        pskt_in = dec["inputs"][input_idx]
        # Calculate the input weight
        # (prevout + sequence + length of scriptSig + scriptsig + 1 byte buffer) * WITNESS_SCALE_FACTOR + num scriptWitness stack items + (length of stack item + stack item) * N stack items + 1 byte buffer
        len_scriptsig = len(pskt_in["final_scriptSig"]["hex"]) // 2 if "final_scriptSig" in pskt_in else 0
        len_scriptsig += len(ser_compact_size(len_scriptsig)) + 1
        len_scriptwitness = (sum([(len(x) // 2) + len(ser_compact_size(len(x) // 2)) for x in pskt_in["final_scriptwitness"]]) + len(pskt_in["final_scriptwitness"]) + 1) if "final_scriptwitness" in pskt_in else 0
        input_weight = ((40 + len_scriptsig) * WITNESS_SCALE_FACTOR) + len_scriptwitness
        low_input_weight = input_weight // 2
        high_input_weight = input_weight * 2

        # Input weight error conditions
        assert_raises_rpc_error(
            -8,
            "Input weights should be specified in inputs rather than in options.",
            wallet.walletcreatefundedpskt,
            inputs=[ext_utxo],
            outputs={self.nodes[0].getnewaddress(): 15},
            options={"input_weights": [{"txid": ext_utxo["txid"], "vout": ext_utxo["vout"], "weight": 1000}]}
        )

        # Funding should also work if the input weight is provided
        pskt = wallet.walletcreatefundedpskt(
            inputs=[{"txid": ext_utxo["txid"], "vout": ext_utxo["vout"], "weight": input_weight}],
            outputs={self.nodes[0].getnewaddress(): 15},
            options={"add_inputs": True}
        )
        signed = wallet.walletprocesspskt(pskt["pskt"])
        signed = self.nodes[0].walletprocesspskt(signed["pskt"])
        final = self.nodes[0].finalizepskt(signed["pskt"])
        assert self.nodes[0].testmempoolaccept([final["hex"]])[0]["allowed"]
        # Reducing the weight should have a lower fee
        pskt2 = wallet.walletcreatefundedpskt(
            inputs=[{"txid": ext_utxo["txid"], "vout": ext_utxo["vout"], "weight": low_input_weight}],
            outputs={self.nodes[0].getnewaddress(): 15},
            options={"add_inputs": True}
        )
        assert_greater_than(pskt["fee"], pskt2["fee"])
        # Increasing the weight should have a higher fee
        pskt2 = wallet.walletcreatefundedpskt(
            inputs=[{"txid": ext_utxo["txid"], "vout": ext_utxo["vout"], "weight": high_input_weight}],
            outputs={self.nodes[0].getnewaddress(): 15},
            options={"add_inputs": True}
        )
        assert_greater_than(pskt2["fee"], pskt["fee"])
        # The provided weight should override the calculated weight when solving data is provided
        pskt3 = wallet.walletcreatefundedpskt(
            inputs=[{"txid": ext_utxo["txid"], "vout": ext_utxo["vout"], "weight": high_input_weight}],
            outputs={self.nodes[0].getnewaddress(): 15},
            options={'add_inputs': True, "solving_data":{"descriptors": [desc]}}
        )
        assert_equal(pskt2["fee"], pskt3["fee"])

        # Import the external utxo descriptor so that we can sign for it from the test wallet
        if self.options.descriptors:
            res = wallet.importdescriptors([{"desc": desc, "timestamp": "now"}])
        else:
            res = wallet.importmulti([{"desc": desc, "timestamp": "now"}])
        assert res[0]["success"]
        # The provided weight should override the calculated weight for a wallet input
        pskt3 = wallet.walletcreatefundedpskt(
            inputs=[{"txid": ext_utxo["txid"], "vout": ext_utxo["vout"], "weight": high_input_weight}],
            outputs={self.nodes[0].getnewaddress(): 15},
            options={"add_inputs": True}
        )
        assert_equal(pskt2["fee"], pskt3["fee"])

        self.log.info("Test signing inputs that the wallet has keys for but is not watching the scripts")
        self.nodes[1].createwallet(wallet_name="scriptwatchonly", disable_private_keys=True)
        watchonly = self.nodes[1].get_wallet_rpc("scriptwatchonly")

        eckey = ECKey()
        eckey.generate()
        privkey = bytes_to_wif(eckey.get_bytes())

        desc = descsum_create("wsh(pkh({}))".format(eckey.get_pubkey().get_bytes().hex()))
        if self.options.descriptors:
            res = watchonly.importdescriptors([{"desc": desc, "timestamp": "now"}])
        else:
            res = watchonly.importmulti([{"desc": desc, "timestamp": "now"}])
        assert res[0]["success"]
        addr = self.nodes[0].deriveaddresses(desc)[0]
        self.nodes[0].sendtoaddress(addr, 10)
        self.generate(self.nodes[0], 1)
        self.nodes[0].importprivkey(privkey)

        pskt = watchonly.sendall([wallet.getnewaddress()])["pskt"]
        pskt = self.nodes[0].walletprocesspskt(pskt)["pskt"]
        self.nodes[0].sendrawtransaction(self.nodes[0].finalizepskt(pskt)["hex"])

        # Same test but for taproot
        if self.options.descriptors:
            eckey = ECKey()
            eckey.generate()
            privkey = bytes_to_wif(eckey.get_bytes())

            desc = descsum_create("tr({},pk({}))".format(H_POINT, eckey.get_pubkey().get_bytes().hex()))
            res = watchonly.importdescriptors([{"desc": desc, "timestamp": "now"}])
            assert res[0]["success"]
            addr = self.nodes[0].deriveaddresses(desc)[0]
            self.nodes[0].sendtoaddress(addr, 10)
            self.generate(self.nodes[0], 1)
            self.nodes[0].importdescriptors([{"desc": descsum_create("tr({})".format(privkey)), "timestamp":"now"}])

            pskt = watchonly.sendall([wallet.getnewaddress(), addr])["pskt"]
            pskt = self.nodes[0].walletprocesspskt(pskt)["pskt"]
            txid = self.nodes[0].sendrawtransaction(self.nodes[0].finalizepskt(pskt)["hex"])
            vout = find_vout_for_address(self.nodes[0], txid, addr)

            # Make sure tap tree is in pskt
            parsed_pskt = PSKT.from_base64(pskt)
            assert_greater_than(len(parsed_pskt.o[vout].map[PSKT_OUT_TAP_TREE]), 0)
            assert "taproot_tree" in self.nodes[0].decodepskt(pskt)["outputs"][vout]
            parsed_pskt.make_blank()
            comb_pskt = self.nodes[0].combinepskt([pskt, parsed_pskt.to_base64()])
            assert_equal(comb_pskt, pskt)

            self.log.info("Test that walletprocesspskt both updates and signs a non-updated pskt containing Taproot inputs")
            addr = self.nodes[0].getnewaddress("", "bech32m")
            txid = self.nodes[0].sendtoaddress(addr, 1)
            vout = find_vout_for_address(self.nodes[0], txid, addr)
            pskt = self.nodes[0].createpskt([{"txid": txid, "vout": vout}], [{self.nodes[0].getnewaddress(): 0.9999}])
            signed = self.nodes[0].walletprocesspskt(pskt)
            rawtx = self.nodes[0].finalizepskt(signed["pskt"])["hex"]
            self.nodes[0].sendrawtransaction(rawtx)
            self.generate(self.nodes[0], 1)

            # Make sure tap tree is not in pskt
            parsed_pskt = PSKT.from_base64(pskt)
            assert PSKT_OUT_TAP_TREE not in parsed_pskt.o[0].map
            assert "taproot_tree" not in self.nodes[0].decodepskt(pskt)["outputs"][0]
            parsed_pskt.make_blank()
            comb_pskt = self.nodes[0].combinepskt([pskt, parsed_pskt.to_base64()])
            assert_equal(comb_pskt, pskt)

        self.log.info("Test decoding PSKT with per-input preimage types")
        # note that the decodepskt RPC doesn't check whether preimages and hashes match
        hash_ripemd160, preimage_ripemd160 = random_bytes(20), random_bytes(50)
        hash_sha256, preimage_sha256 = random_bytes(32), random_bytes(50)
        hash_hash160, preimage_hash160 = random_bytes(20), random_bytes(50)
        hash_hash256, preimage_hash256 = random_bytes(32), random_bytes(50)

        tx = CTransaction()
        tx.vin = [CTxIn(outpoint=COutPoint(hash=int('aa' * 32, 16), n=0), scriptSig=b""),
                  CTxIn(outpoint=COutPoint(hash=int('bb' * 32, 16), n=0), scriptSig=b""),
                  CTxIn(outpoint=COutPoint(hash=int('cc' * 32, 16), n=0), scriptSig=b""),
                  CTxIn(outpoint=COutPoint(hash=int('dd' * 32, 16), n=0), scriptSig=b"")]
        tx.vout = [CTxOut(nValue=0, scriptPubKey=b"")]
        pskt = PSKT()
        pskt.g = PSKTMap({PSKT_GLOBAL_UNSIGNED_TX: tx.serialize()})
        pskt.i = [PSKTMap({bytes([PSKT_IN_RIPEMD160]) + hash_ripemd160: preimage_ripemd160}),
                  PSKTMap({bytes([PSKT_IN_SHA256]) + hash_sha256: preimage_sha256}),
                  PSKTMap({bytes([PSKT_IN_HASH160]) + hash_hash160: preimage_hash160}),
                  PSKTMap({bytes([PSKT_IN_HASH256]) + hash_hash256: preimage_hash256})]
        pskt.o = [PSKTMap()]
        res_inputs = self.nodes[0].decodepskt(pskt.to_base64())["inputs"]
        assert_equal(len(res_inputs), 4)
        preimage_keys = ["ripemd160_preimages", "sha256_preimages", "hash160_preimages", "hash256_preimages"]
        expected_hashes = [hash_ripemd160, hash_sha256, hash_hash160, hash_hash256]
        expected_preimages = [preimage_ripemd160, preimage_sha256, preimage_hash160, preimage_hash256]
        for res_input, preimage_key, hash, preimage in zip(res_inputs, preimage_keys, expected_hashes, expected_preimages):
            assert preimage_key in res_input
            assert_equal(len(res_input[preimage_key]), 1)
            assert hash.hex() in res_input[preimage_key]
            assert_equal(res_input[preimage_key][hash.hex()], preimage.hex())

        self.log.info("Test that combining PSKTs with different transactions fails")
        tx = CTransaction()
        tx.vin = [CTxIn(outpoint=COutPoint(hash=int('aa' * 32, 16), n=0), scriptSig=b"")]
        tx.vout = [CTxOut(nValue=0, scriptPubKey=b"")]
        pskt1 = PSKT(g=PSKTMap({PSKT_GLOBAL_UNSIGNED_TX: tx.serialize()}), i=[PSKTMap()], o=[PSKTMap()]).to_base64()
        tx.vout[0].nValue += 1  # slightly modify tx
        pskt2 = PSKT(g=PSKTMap({PSKT_GLOBAL_UNSIGNED_TX: tx.serialize()}), i=[PSKTMap()], o=[PSKTMap()]).to_base64()
        assert_raises_rpc_error(-8, "PSKTs not compatible (different transactions)", self.nodes[0].combinepskt, [pskt1, pskt2])
        assert_equal(self.nodes[0].combinepskt([pskt1, pskt1]), pskt1)


if __name__ == '__main__':
    PSKTTest().main()
