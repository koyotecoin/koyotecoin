// Copyright (c) 2009-2021 The Bitcoin Core developers
// Copyright (c) 2023-2023 The Koyotecoin Core developers
// Distributed under the MIT software license, see the accompanying
// file COPYING or http://www.opensource.org/licenses/mit-license.php.

#include <pskt.h>

#include <util/check.h>
#include <util/strencodings.h>


PartiallySignedTransaction::PartiallySignedTransaction(const CMutableTransaction& tx) : tx(tx)
{
    inputs.resize(tx.vin.size());
    outputs.resize(tx.vout.size());
}

bool PartiallySignedTransaction::IsNull() const
{
    return !tx && inputs.empty() && outputs.empty() && unknown.empty();
}

bool PartiallySignedTransaction::Merge(const PartiallySignedTransaction& pskt)
{
    // Prohibited to merge two PSKTs over different transactions
    if (tx->GetHash() != pskt.tx->GetHash()) {
        return false;
    }

    for (unsigned int i = 0; i < inputs.size(); ++i) {
        inputs[i].Merge(pskt.inputs[i]);
    }
    for (unsigned int i = 0; i < outputs.size(); ++i) {
        outputs[i].Merge(pskt.outputs[i]);
    }
    for (auto& xpub_pair : pskt.m_xpubs) {
        if (m_xpubs.count(xpub_pair.first) == 0) {
            m_xpubs[xpub_pair.first] = xpub_pair.second;
        } else {
            m_xpubs[xpub_pair.first].insert(xpub_pair.second.begin(), xpub_pair.second.end());
        }
    }
    unknown.insert(pskt.unknown.begin(), pskt.unknown.end());

    return true;
}

bool PartiallySignedTransaction::AddInput(const CTxIn& txin, PSKTInput& psktin)
{
    if (std::find(tx->vin.begin(), tx->vin.end(), txin) != tx->vin.end()) {
        return false;
    }
    tx->vin.push_back(txin);
    psktin.partial_sigs.clear();
    psktin.final_script_sig.clear();
    psktin.final_script_witness.SetNull();
    inputs.push_back(psktin);
    return true;
}

bool PartiallySignedTransaction::AddOutput(const CTxOut& txout, const PSKTOutput& psktout)
{
    tx->vout.push_back(txout);
    outputs.push_back(psktout);
    return true;
}

bool PartiallySignedTransaction::GetInputUTXO(CTxOut& utxo, int input_index) const
{
    const PSKTInput& input = inputs[input_index];
    uint32_t prevout_index = tx->vin[input_index].prevout.n;
    if (input.non_witness_utxo) {
        if (prevout_index >= input.non_witness_utxo->vout.size()) {
            return false;
        }
        if (input.non_witness_utxo->GetHash() != tx->vin[input_index].prevout.hash) {
            return false;
        }
        utxo = input.non_witness_utxo->vout[prevout_index];
    } else if (!input.witness_utxo.IsNull()) {
        utxo = input.witness_utxo;
    } else {
        return false;
    }
    return true;
}

bool PSKTInput::IsNull() const
{
    return !non_witness_utxo && witness_utxo.IsNull() && partial_sigs.empty() && unknown.empty() && hd_keypaths.empty() && redeem_script.empty() && witness_script.empty();
}

void PSKTInput::FillSignatureData(SignatureData& sigdata) const
{
    if (!final_script_sig.empty()) {
        sigdata.scriptSig = final_script_sig;
        sigdata.complete = true;
    }
    if (!final_script_witness.IsNull()) {
        sigdata.scriptWitness = final_script_witness;
        sigdata.complete = true;
    }
    if (sigdata.complete) {
        return;
    }

    sigdata.signatures.insert(partial_sigs.begin(), partial_sigs.end());
    if (!redeem_script.empty()) {
        sigdata.redeem_script = redeem_script;
    }
    if (!witness_script.empty()) {
        sigdata.witness_script = witness_script;
    }
    for (const auto& key_pair : hd_keypaths) {
        sigdata.misc_pubkeys.emplace(key_pair.first.GetID(), key_pair);
    }
    if (!m_tap_key_sig.empty()) {
        sigdata.taproot_key_path_sig = m_tap_key_sig;
    }
    for (const auto& [pubkey_leaf, sig] : m_tap_script_sigs) {
        sigdata.taproot_script_sigs.emplace(pubkey_leaf, sig);
    }
    if (!m_tap_internal_key.IsNull()) {
        sigdata.tr_spenddata.internal_key = m_tap_internal_key;
    }
    if (!m_tap_merkle_root.IsNull()) {
        sigdata.tr_spenddata.merkle_root = m_tap_merkle_root;
    }
    for (const auto& [leaf_script, control_block] : m_tap_scripts) {
        sigdata.tr_spenddata.scripts.emplace(leaf_script, control_block);
    }
    for (const auto& [pubkey, leaf_origin] : m_tap_bip32_paths) {
        sigdata.taproot_misc_pubkeys.emplace(pubkey, leaf_origin);
    }
}

void PSKTInput::FromSignatureData(const SignatureData& sigdata)
{
    if (sigdata.complete) {
        partial_sigs.clear();
        hd_keypaths.clear();
        redeem_script.clear();
        witness_script.clear();

        if (!sigdata.scriptSig.empty()) {
            final_script_sig = sigdata.scriptSig;
        }
        if (!sigdata.scriptWitness.IsNull()) {
            final_script_witness = sigdata.scriptWitness;
        }
        return;
    }

    partial_sigs.insert(sigdata.signatures.begin(), sigdata.signatures.end());
    if (redeem_script.empty() && !sigdata.redeem_script.empty()) {
        redeem_script = sigdata.redeem_script;
    }
    if (witness_script.empty() && !sigdata.witness_script.empty()) {
        witness_script = sigdata.witness_script;
    }
    for (const auto& entry : sigdata.misc_pubkeys) {
        hd_keypaths.emplace(entry.second);
    }
    if (!sigdata.taproot_key_path_sig.empty()) {
        m_tap_key_sig = sigdata.taproot_key_path_sig;
    }
    for (const auto& [pubkey_leaf, sig] : sigdata.taproot_script_sigs) {
        m_tap_script_sigs.emplace(pubkey_leaf, sig);
    }
    if (!sigdata.tr_spenddata.internal_key.IsNull()) {
        m_tap_internal_key = sigdata.tr_spenddata.internal_key;
    }
    if (!sigdata.tr_spenddata.merkle_root.IsNull()) {
        m_tap_merkle_root = sigdata.tr_spenddata.merkle_root;
    }
    for (const auto& [leaf_script, control_block] : sigdata.tr_spenddata.scripts) {
        m_tap_scripts.emplace(leaf_script, control_block);
    }
    for (const auto& [pubkey, leaf_origin] : sigdata.taproot_misc_pubkeys) {
        m_tap_bip32_paths.emplace(pubkey, leaf_origin);
    }
}

void PSKTInput::Merge(const PSKTInput& input)
{
    if (!non_witness_utxo && input.non_witness_utxo) non_witness_utxo = input.non_witness_utxo;
    if (witness_utxo.IsNull() && !input.witness_utxo.IsNull()) {
        witness_utxo = input.witness_utxo;
    }

    partial_sigs.insert(input.partial_sigs.begin(), input.partial_sigs.end());
    ripemd160_preimages.insert(input.ripemd160_preimages.begin(), input.ripemd160_preimages.end());
    sha256_preimages.insert(input.sha256_preimages.begin(), input.sha256_preimages.end());
    hash160_preimages.insert(input.hash160_preimages.begin(), input.hash160_preimages.end());
    hash256_preimages.insert(input.hash256_preimages.begin(), input.hash256_preimages.end());
    hd_keypaths.insert(input.hd_keypaths.begin(), input.hd_keypaths.end());
    unknown.insert(input.unknown.begin(), input.unknown.end());
    m_tap_script_sigs.insert(input.m_tap_script_sigs.begin(), input.m_tap_script_sigs.end());
    m_tap_scripts.insert(input.m_tap_scripts.begin(), input.m_tap_scripts.end());
    m_tap_bip32_paths.insert(input.m_tap_bip32_paths.begin(), input.m_tap_bip32_paths.end());

    if (redeem_script.empty() && !input.redeem_script.empty()) redeem_script = input.redeem_script;
    if (witness_script.empty() && !input.witness_script.empty()) witness_script = input.witness_script;
    if (final_script_sig.empty() && !input.final_script_sig.empty()) final_script_sig = input.final_script_sig;
    if (final_script_witness.IsNull() && !input.final_script_witness.IsNull()) final_script_witness = input.final_script_witness;
    if (m_tap_key_sig.empty() && !input.m_tap_key_sig.empty()) m_tap_key_sig = input.m_tap_key_sig;
    if (m_tap_internal_key.IsNull() && !input.m_tap_internal_key.IsNull()) m_tap_internal_key = input.m_tap_internal_key;
    if (m_tap_merkle_root.IsNull() && !input.m_tap_merkle_root.IsNull()) m_tap_merkle_root = input.m_tap_merkle_root;
}

void PSKTOutput::FillSignatureData(SignatureData& sigdata) const
{
    if (!redeem_script.empty()) {
        sigdata.redeem_script = redeem_script;
    }
    if (!witness_script.empty()) {
        sigdata.witness_script = witness_script;
    }
    for (const auto& key_pair : hd_keypaths) {
        sigdata.misc_pubkeys.emplace(key_pair.first.GetID(), key_pair);
    }
    if (!m_tap_tree.empty() && m_tap_internal_key.IsFullyValid()) {
        TaprootBuilder builder;
        for (const auto& [depth, leaf_ver, script] : m_tap_tree) {
            builder.Add((int)depth, script, (int)leaf_ver, /*track=*/true);
        }
        assert(builder.IsComplete());
        builder.Finalize(m_tap_internal_key);
        TaprootSpendData spenddata = builder.GetSpendData();

        sigdata.tr_spenddata.internal_key = m_tap_internal_key;
        sigdata.tr_spenddata.Merge(spenddata);
    }
    for (const auto& [pubkey, leaf_origin] : m_tap_bip32_paths) {
        sigdata.taproot_misc_pubkeys.emplace(pubkey, leaf_origin);
    }
}

void PSKTOutput::FromSignatureData(const SignatureData& sigdata)
{
    if (redeem_script.empty() && !sigdata.redeem_script.empty()) {
        redeem_script = sigdata.redeem_script;
    }
    if (witness_script.empty() && !sigdata.witness_script.empty()) {
        witness_script = sigdata.witness_script;
    }
    for (const auto& entry : sigdata.misc_pubkeys) {
        hd_keypaths.emplace(entry.second);
    }
    if (!sigdata.tr_spenddata.internal_key.IsNull()) {
        m_tap_internal_key = sigdata.tr_spenddata.internal_key;
    }
    if (sigdata.tr_builder.has_value() && sigdata.tr_builder->HasScripts()) {
        m_tap_tree = sigdata.tr_builder->GetTreeTuples();
    }
    for (const auto& [pubkey, leaf_origin] : sigdata.taproot_misc_pubkeys) {
        m_tap_bip32_paths.emplace(pubkey, leaf_origin);
    }
}

bool PSKTOutput::IsNull() const
{
    return redeem_script.empty() && witness_script.empty() && hd_keypaths.empty() && unknown.empty();
}

void PSKTOutput::Merge(const PSKTOutput& output)
{
    hd_keypaths.insert(output.hd_keypaths.begin(), output.hd_keypaths.end());
    unknown.insert(output.unknown.begin(), output.unknown.end());
    m_tap_bip32_paths.insert(output.m_tap_bip32_paths.begin(), output.m_tap_bip32_paths.end());

    if (redeem_script.empty() && !output.redeem_script.empty()) redeem_script = output.redeem_script;
    if (witness_script.empty() && !output.witness_script.empty()) witness_script = output.witness_script;
    if (m_tap_internal_key.IsNull() && !output.m_tap_internal_key.IsNull()) m_tap_internal_key = output.m_tap_internal_key;
    if (m_tap_tree.empty() && !output.m_tap_tree.empty()) m_tap_tree = output.m_tap_tree;
}
bool PSKTInputSigned(const PSKTInput& input)
{
    return !input.final_script_sig.empty() || !input.final_script_witness.IsNull();
}

size_t CountPSKTUnsignedInputs(const PartiallySignedTransaction& pskt) {
    size_t count = 0;
    for (const auto& input : pskt.inputs) {
        if (!PSKTInputSigned(input)) {
            count++;
        }
    }

    return count;
}

void UpdatePSKTOutput(const SigningProvider& provider, PartiallySignedTransaction& pskt, int index)
{
    CMutableTransaction& tx = *Assert(pskt.tx);
    const CTxOut& out = tx.vout.at(index);
    PSKTOutput& pskt_out = pskt.outputs.at(index);

    // Fill a SignatureData with output info
    SignatureData sigdata;
    pskt_out.FillSignatureData(sigdata);

    // Construct a would-be spend of this output, to update sigdata with.
    // Note that ProduceSignature is used to fill in metadata (not actual signatures),
    // so provider does not need to provide any private keys (it can be a HidingSigningProvider).
    MutableTransactionSignatureCreator creator(tx, /*input_idx=*/0, out.nValue, SIGHASH_ALL);
    ProduceSignature(provider, creator, out.scriptPubKey, sigdata);

    // Put redeem_script, witness_script, key paths, into PSKTOutput.
    pskt_out.FromSignatureData(sigdata);
}

PrecomputedTransactionData PrecomputePSKTData(const PartiallySignedTransaction& pskt)
{
    const CMutableTransaction& tx = *pskt.tx;
    bool have_all_spent_outputs = true;
    std::vector<CTxOut> utxos(tx.vin.size());
    for (size_t idx = 0; idx < tx.vin.size(); ++idx) {
        if (!pskt.GetInputUTXO(utxos[idx], idx)) have_all_spent_outputs = false;
    }
    PrecomputedTransactionData txdata;
    if (have_all_spent_outputs) {
        txdata.Init(tx, std::move(utxos), true);
    } else {
        txdata.Init(tx, {}, true);
    }
    return txdata;
}

bool SignPSKTInput(const SigningProvider& provider, PartiallySignedTransaction& pskt, int index, const PrecomputedTransactionData* txdata, int sighash,  SignatureData* out_sigdata, bool finalize)
{
    PSKTInput& input = pskt.inputs.at(index);
    const CMutableTransaction& tx = *pskt.tx;

    if (PSKTInputSigned(input)) {
        return true;
    }

    // Fill SignatureData with input info
    SignatureData sigdata;
    input.FillSignatureData(sigdata);

    // Get UTXO
    bool require_witness_sig = false;
    CTxOut utxo;

    if (input.non_witness_utxo) {
        // If we're taking our information from a non-witness UTXO, verify that it matches the prevout.
        COutPoint prevout = tx.vin[index].prevout;
        if (prevout.n >= input.non_witness_utxo->vout.size()) {
            return false;
        }
        if (input.non_witness_utxo->GetHash() != prevout.hash) {
            return false;
        }
        utxo = input.non_witness_utxo->vout[prevout.n];
    } else if (!input.witness_utxo.IsNull()) {
        utxo = input.witness_utxo;
        // When we're taking our information from a witness UTXO, we can't verify it is actually data from
        // the output being spent. This is safe in case a witness signature is produced (which includes this
        // information directly in the hash), but not for non-witness signatures. Remember that we require
        // a witness signature in this situation.
        require_witness_sig = true;
    } else {
        return false;
    }

    sigdata.witness = false;
    bool sig_complete;
    if (txdata == nullptr) {
        sig_complete = ProduceSignature(provider, DUMMY_SIGNATURE_CREATOR, utxo.scriptPubKey, sigdata);
    } else {
        MutableTransactionSignatureCreator creator(tx, index, utxo.nValue, txdata, sighash);
        sig_complete = ProduceSignature(provider, creator, utxo.scriptPubKey, sigdata);
    }
    // Verify that a witness signature was produced in case one was required.
    if (require_witness_sig && !sigdata.witness) return false;

    // If we are not finalizing, set sigdata.complete to false to not set the scriptWitness
    if (!finalize && sigdata.complete) sigdata.complete = false;

    input.FromSignatureData(sigdata);

    // If we have a witness signature, put a witness UTXO.
    if (sigdata.witness) {
        input.witness_utxo = utxo;
        // We can remove the non_witness_utxo if and only if there are no non-segwit or segwit v0
        // inputs in this transaction. Since this requires inspecting the entire transaction, this
        // is something for the caller to deal with (i.e. FillPSKT).
    }

    // Fill in the missing info
    if (out_sigdata) {
        out_sigdata->missing_pubkeys = sigdata.missing_pubkeys;
        out_sigdata->missing_sigs = sigdata.missing_sigs;
        out_sigdata->missing_redeem_script = sigdata.missing_redeem_script;
        out_sigdata->missing_witness_script = sigdata.missing_witness_script;
    }

    return sig_complete;
}

bool FinalizePSKT(PartiallySignedTransaction& psktx)
{
    // Finalize input signatures -- in case we have partial signatures that add up to a complete
    //   signature, but have not combined them yet (e.g. because the combiner that created this
    //   PartiallySignedTransaction did not understand them), this will combine them into a final
    //   script.
    bool complete = true;
    const PrecomputedTransactionData txdata = PrecomputePSKTData(psktx);
    for (unsigned int i = 0; i < psktx.tx->vin.size(); ++i) {
        complete &= SignPSKTInput(DUMMY_SIGNING_PROVIDER, psktx, i, &txdata, SIGHASH_ALL, nullptr, true);
    }

    return complete;
}

bool FinalizeAndExtractPSKT(PartiallySignedTransaction& psktx, CMutableTransaction& result)
{
    // It's not safe to extract a PSKT that isn't finalized, and there's no easy way to check
    //   whether a PSKT is finalized without finalizing it, so we just do this.
    if (!FinalizePSKT(psktx)) {
        return false;
    }

    result = *psktx.tx;
    for (unsigned int i = 0; i < result.vin.size(); ++i) {
        result.vin[i].scriptSig = psktx.inputs[i].final_script_sig;
        result.vin[i].scriptWitness = psktx.inputs[i].final_script_witness;
    }
    return true;
}

TransactionError CombinePSKTs(PartiallySignedTransaction& out, const std::vector<PartiallySignedTransaction>& psktxs)
{
    out = psktxs[0]; // Copy the first one

    // Merge
    for (auto it = std::next(psktxs.begin()); it != psktxs.end(); ++it) {
        if (!out.Merge(*it)) {
            return TransactionError::PSKT_MISMATCH;
        }
    }
    return TransactionError::OK;
}

std::string PSKTRoleName(PSKTRole role) {
    switch (role) {
    case PSKTRole::CREATOR: return "creator";
    case PSKTRole::UPDATER: return "updater";
    case PSKTRole::SIGNER: return "signer";
    case PSKTRole::FINALIZER: return "finalizer";
    case PSKTRole::EXTRACTOR: return "extractor";
        // no default case, so the compiler can warn about missing cases
    }
    assert(false);
}

bool DecodeBase64PSKT(PartiallySignedTransaction& pskt, const std::string& base64_tx, std::string& error)
{
    auto tx_data = DecodeBase64(base64_tx);
    if (!tx_data) {
        error = "invalid base64";
        return false;
    }
    return DecodeRawPSKT(pskt, MakeByteSpan(*tx_data), error);
}

bool DecodeRawPSKT(PartiallySignedTransaction& pskt, Span<const std::byte> tx_data, std::string& error)
{
    CDataStream ss_data(tx_data, SER_NETWORK, PROTOCOL_VERSION);
    try {
        ss_data >> pskt;
        if (!ss_data.empty()) {
            error = "extra data after PSKT";
            return false;
        }
    } catch (const std::exception& e) {
        error = e.what();
        return false;
    }
    return true;
}

uint32_t PartiallySignedTransaction::GetVersion() const
{
    if (m_version != std::nullopt) {
        return *m_version;
    }
    return 0;
}
