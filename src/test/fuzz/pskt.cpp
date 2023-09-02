// Copyright (c) 2019-2021 The Bitcoin Core developers
// Copyright (c) 2023-2023 The Koyotecoin Core developers
// Distributed under the MIT software license, see the accompanying
// file COPYING or http://www.opensource.org/licenses/mit-license.php.

#include <test/fuzz/FuzzedDataProvider.h>
#include <test/fuzz/fuzz.h>

#include <node/pskt.h>
#include <pskt.h>
#include <pubkey.h>
#include <script/script.h>
#include <streams.h>
#include <util/check.h>
#include <version.h>

#include <cstdint>
#include <optional>
#include <string>
#include <vector>

using node::AnalyzePSKT;
using node::PSKTAnalysis;
using node::PSKTInputAnalysis;

void initialize_pskt()
{
    static const ECCVerifyHandle verify_handle;
}

FUZZ_TARGET_INIT(pskt, initialize_pskt)
{
    FuzzedDataProvider fuzzed_data_provider{buffer.data(), buffer.size()};
    PartiallySignedTransaction pskt_mut;
    std::string error;
    auto str = fuzzed_data_provider.ConsumeRandomLengthString();
    if (!DecodeRawPSKT(pskt_mut, MakeByteSpan(str), error)) {
        return;
    }
    const PartiallySignedTransaction pskt = pskt_mut;

    const PSKTAnalysis analysis = AnalyzePSKT(pskt);
    (void)PSKTRoleName(analysis.next);
    for (const PSKTInputAnalysis& input_analysis : analysis.inputs) {
        (void)PSKTRoleName(input_analysis.next);
    }

    (void)pskt.IsNull();

    std::optional<CMutableTransaction> tx = pskt.tx;
    if (tx) {
        const CMutableTransaction& mtx = *tx;
        const PartiallySignedTransaction pskt_from_tx{mtx};
    }

    for (const PSKTInput& input : pskt.inputs) {
        (void)PSKTInputSigned(input);
        (void)input.IsNull();
    }
    (void)CountPSKTUnsignedInputs(pskt);

    for (const PSKTOutput& output : pskt.outputs) {
        (void)output.IsNull();
    }

    for (size_t i = 0; i < pskt.tx->vin.size(); ++i) {
        CTxOut tx_out;
        if (pskt.GetInputUTXO(tx_out, i)) {
            (void)tx_out.IsNull();
            (void)tx_out.ToString();
        }
    }

    pskt_mut = pskt;
    (void)FinalizePSKT(pskt_mut);

    pskt_mut = pskt;
    CMutableTransaction result;
    if (FinalizeAndExtractPSKT(pskt_mut, result)) {
        const PartiallySignedTransaction pskt_from_tx{result};
    }

    PartiallySignedTransaction pskt_merge;
    str = fuzzed_data_provider.ConsumeRandomLengthString();
    if (!DecodeRawPSKT(pskt_merge, MakeByteSpan(str), error)) {
        pskt_merge = pskt;
    }
    pskt_mut = pskt;
    (void)pskt_mut.Merge(pskt_merge);
    pskt_mut = pskt;
    (void)CombinePSKTs(pskt_mut, {pskt_mut, pskt_merge});
    pskt_mut = pskt;
    for (unsigned int i = 0; i < pskt_merge.tx->vin.size(); ++i) {
        (void)pskt_mut.AddInput(pskt_merge.tx->vin[i], pskt_merge.inputs[i]);
    }
    for (unsigned int i = 0; i < pskt_merge.tx->vout.size(); ++i) {
        Assert(pskt_mut.AddOutput(pskt_merge.tx->vout[i], pskt_merge.outputs[i]));
    }
    pskt_mut.unknown.insert(pskt_merge.unknown.begin(), pskt_merge.unknown.end());
}
