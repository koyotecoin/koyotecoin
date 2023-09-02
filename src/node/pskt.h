// Copyright (c) 2009-2021 The Bitcoin Core developers
// Copyright (c) 2023-2023 The Koyotecoin Core developers
// Distributed under the MIT software license, see the accompanying
// file COPYING or http://www.opensource.org/licenses/mit-license.php.

#ifndef KOYOTECOIN_NODE_PSKT_H
#define KOYOTECOIN_NODE_PSKT_H

#include <pskt.h>

#include <optional>

namespace node {
/**
 * Holds an analysis of one input from a PSKT
 */
struct PSKTInputAnalysis {
    bool has_utxo; //!< Whether we have UTXO information for this input
    bool is_final; //!< Whether the input has all required information including signatures
    PSKTRole next; //!< Which of the BIP 174 roles needs to handle this input next

    std::vector<CKeyID> missing_pubkeys; //!< Pubkeys whose BIP32 derivation path is missing
    std::vector<CKeyID> missing_sigs;    //!< Pubkeys whose signatures are missing
    uint160 missing_redeem_script;       //!< Hash160 of redeem script, if missing
    uint256 missing_witness_script;      //!< SHA256 of witness script, if missing
};

/**
 * Holds the results of AnalyzePSKT (miscellaneous information about a PSKT)
 */
struct PSKTAnalysis {
    std::optional<size_t> estimated_vsize;      //!< Estimated weight of the transaction
    std::optional<CFeeRate> estimated_feerate;  //!< Estimated feerate (fee / weight) of the transaction
    std::optional<CAmount> fee;                 //!< Amount of fee being paid by the transaction
    std::vector<PSKTInputAnalysis> inputs;      //!< More information about the individual inputs of the transaction
    PSKTRole next;                              //!< Which of the BIP 174 roles needs to handle the transaction next
    std::string error;                          //!< Error message

    void SetInvalid(std::string err_msg)
    {
        estimated_vsize = std::nullopt;
        estimated_feerate = std::nullopt;
        fee = std::nullopt;
        inputs.clear();
        next = PSKTRole::CREATOR;
        error = err_msg;
    }
};

/**
 * Provides helpful miscellaneous information about where a PSKT is in the signing workflow.
 *
 * @param[in] psktx the PSKT to analyze
 * @return A PSKTAnalysis with information about the provided PSKT.
 */
PSKTAnalysis AnalyzePSKT(PartiallySignedTransaction psktx);
} // namespace node

#endif // KOYOTECOIN_NODE_PSKT_H
