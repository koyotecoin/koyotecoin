// Copyright (c) 2009-2010 Satoshi Nakamoto
// Copyright (c) 2009-2021 The Bitcoin Core developers
// Copyright (c) 2023-2023 The Koyotecoin Core developers
// Distributed under the MIT software license, see the accompanying
// file COPYING or http://www.opensource.org/licenses/mit-license.php.

#include <consensus/amount.h>
#include <policy/feerate.h>
#include <tinyformat.h>

#include <cmath>

CFeeRate::CFeeRate(const CAmount& nFeePaid, uint32_t num_bytes)
{
    const int64_t nSize{num_bytes};

    if (nSize > 0) {
        nHowloshisPerK = nFeePaid * 1000 / nSize;
    } else {
        nHowloshisPerK = 0;
    }
}

CAmount CFeeRate::GetFee(uint32_t num_bytes) const
{
    const int64_t nSize{num_bytes};

    // Be explicit that we're converting from a double to int64_t (CAmount) here.
    // We've previously had issues with the silent double->int64_t conversion.
    CAmount nFee{static_cast<CAmount>(std::ceil(nHowloshisPerK * nSize / 1000.0))};

    if (nFee == 0 && nSize != 0) {
        if (nHowloshisPerK > 0) nFee = CAmount(1);
        if (nHowloshisPerK < 0) nFee = CAmount(-1);
    }

    return nFee;
}

std::string CFeeRate::ToString(const FeeEstimateMode& fee_estimate_mode) const
{
    switch (fee_estimate_mode) {
    case FeeEstimateMode::HOWL_VB: return strprintf("%d.%03d %s/vB", nHowloshisPerK / 1000, nHowloshisPerK % 1000, CURRENCY_ATOM);
    default:                      return strprintf("%d.%08d %s/kvB", nHowloshisPerK / COIN, nHowloshisPerK % COIN, CURRENCY_UNIT);
    }
}
