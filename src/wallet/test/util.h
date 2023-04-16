// Copyright (c) 2021 The Bitcoin Core developers
// Copyright (c) 2023-2023 The Koyotecoin Core developers
// Distributed under the MIT software license, see the accompanying
// file COPYING or http://www.opensource.org/licenses/mit-license.php.

#ifndef KOYOTECOIN_WALLET_TEST_UTIL_H
#define KOYOTECOIN_WALLET_TEST_UTIL_H

#include <memory>

class ArgsManager;
class CChain;
class CKey;
namespace interfaces {
class Chain;
} // namespace interfaces

namespace wallet {
class CWallet;

std::unique_ptr<CWallet> CreateSyncedWallet(interfaces::Chain& chain, CChain& cchain, ArgsManager& args, const CKey& key);
} // namespace wallet

#endif // KOYOTECOIN_WALLET_TEST_UTIL_H
