// Copyright (c) 2022 The Bitcoin Core developers
// Copyright (c) 2023-2023 The Koyotecoin Core developers
// Distributed under the MIT software license, see the accompanying
// file COPYING or http://www.opensource.org/licenses/mit-license.php.

#ifndef KOYOTECOIN_POLICY_FEES_ARGS_H
#define KOYOTECOIN_POLICY_FEES_ARGS_H

#include <fs.h>

class ArgsManager;

/** @return The fee estimates data file path. */
fs::path FeeestPath(const ArgsManager& argsman);

#endif // KOYOTECOIN_POLICY_FEES_ARGS_H
