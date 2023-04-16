// Copyright (c) 2020 The Bitcoin Core developers
// Copyright (c) 2023-2023 The Koyotecoin Core developers
// Distributed under the MIT software license, see the accompanying
// file COPYING or http://www.opensource.org/licenses/mit-license.php.

#ifndef KOYOTECOIN_TEST_UTIL_VALIDATION_H
#define KOYOTECOIN_TEST_UTIL_VALIDATION_H

#include <validation.h>

class CValidationInterface;

struct TestChainState : public Chainstate {
    /** Reset the ibd cache to its initial state */
    void ResetIbd();
    /** Toggle IsInitialBlockDownload from true to false */
    void JumpOutOfIbd();
};

class ValidationInterfaceTest
{
public:
    static void BlockConnected(CValidationInterface& obj, const std::shared_ptr<const CBlock>& block, const CBlockIndex* pindex);
};

#endif // KOYOTECOIN_TEST_UTIL_VALIDATION_H
