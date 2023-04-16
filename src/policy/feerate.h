// Copyright (c) 2009-2010 Satoshi Nakamoto
// Copyright (c) 2009-2021 The Bitcoin Core developers
// Copyright (c) 2023-2023 The Koyotecoin Core developers
// Distributed under the MIT software license, see the accompanying
// file COPYING or http://www.opensource.org/licenses/mit-license.php.

#ifndef KOYOTECOIN_POLICY_FEERATE_H
#define KOYOTECOIN_POLICY_FEERATE_H

#include <consensus/amount.h>
#include <serialize.h>


#include <cstdint>
#include <string>
#include <type_traits>

const std::string CURRENCY_UNIT = "KYC";  // One formatted unit
const std::string CURRENCY_ATOM = "howl"; // One indivisible minimum value unit

/* Used to determine type of fee estimation requested */
enum class FeeEstimateMode {
    UNSET,        //!< Use default settings based on other criteria
    ECONOMICAL,   //!< Force estimateSmartFee to use non-conservative estimates
    CONSERVATIVE, //!< Force estimateSmartFee to use conservative estimates
    KYC_KVB,      //!< Use KYC/kvB fee rate unit
    HOWL_VB,      //!< Use howl/vB fee rate unit
};

/**
 * Fee rate in howloshis per kilovirtualbyte: CAmount / kvB
 */
class CFeeRate
{
private:
    /** Fee rate in howl/kvB (howloshis per 1000 virtualbytes) */
    CAmount nHowloshisPerK;

public:
    /** Fee rate of 0 howloshis per kvB */
    CFeeRate() : nHowloshisPerK(0) {}
    template <typename I>
    explicit CFeeRate(const I _nHowloshisPerK) : nHowloshisPerK(_nHowloshisPerK)
    {
        // We've previously had bugs creep in from silent double->int conversion...
        static_assert(std::is_integral<I>::value, "CFeeRate should be used without floats");
    }

    /**
     * Construct a fee rate from a fee in howloshis and a vsize in vB.
     *
     * param@[in]   nFeePaid    The fee paid by a transaction, in howloshis
     * param@[in]   num_bytes   The vsize of a transaction, in vbytes
     */
    CFeeRate(const CAmount& nFeePaid, uint32_t num_bytes);

    /**
     * Return the fee in howloshis for the given vsize in vbytes.
     * If the calculated fee would have fractional howloshis, then the
     * returned fee will always be rounded up to the nearest howloshi.
     */
    CAmount GetFee(uint32_t num_bytes) const;

    /**
     * Return the fee in howloshis for a vsize of 1000 vbytes
     */
    CAmount GetFeePerK() const { return GetFee(1000); }
    friend bool operator<(const CFeeRate& a, const CFeeRate& b) { return a.nHowloshisPerK < b.nHowloshisPerK; }
    friend bool operator>(const CFeeRate& a, const CFeeRate& b) { return a.nHowloshisPerK > b.nHowloshisPerK; }
    friend bool operator==(const CFeeRate& a, const CFeeRate& b) { return a.nHowloshisPerK == b.nHowloshisPerK; }
    friend bool operator<=(const CFeeRate& a, const CFeeRate& b) { return a.nHowloshisPerK <= b.nHowloshisPerK; }
    friend bool operator>=(const CFeeRate& a, const CFeeRate& b) { return a.nHowloshisPerK >= b.nHowloshisPerK; }
    friend bool operator!=(const CFeeRate& a, const CFeeRate& b) { return a.nHowloshisPerK != b.nHowloshisPerK; }
    CFeeRate& operator+=(const CFeeRate& a)
    {
        nHowloshisPerK += a.nHowloshisPerK;
        return *this;
    }
    std::string ToString(const FeeEstimateMode& fee_estimate_mode = FeeEstimateMode::KYC_KVB) const;

    SERIALIZE_METHODS(CFeeRate, obj) { READWRITE(obj.nHowloshisPerK); }
};

#endif // KOYOTECOIN_POLICY_FEERATE_H
