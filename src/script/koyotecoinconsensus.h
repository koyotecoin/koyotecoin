// Copyright (c) 2009-2010 Satoshi Nakamoto
// Copyright (c) 2009-2020 The Bitcoin Core developers
// Copyright (c) 2023-2023 The Koyotecoin Core developers
// Distributed under the MIT software license, see the accompanying
// file COPYING or http://www.opensource.org/licenses/mit-license.php.

#ifndef KOYOTECOIN_SCRIPT_KOYOTECOINCONSENSUS_H
#define KOYOTECOIN_SCRIPT_KOYOTECOINCONSENSUS_H

#include <stdint.h>

#if defined(BUILD_KOYOTECOIN_INTERNAL) && defined(HAVE_CONFIG_H)
#include <config/koyotecoin-config.h>
  #if defined(_WIN32)
    #if defined(HAVE_DLLEXPORT_ATTRIBUTE)
      #define EXPORT_SYMBOL __declspec(dllexport)
    #else
      #define EXPORT_SYMBOL
    #endif
  #elif defined(HAVE_DEFAULT_VISIBILITY_ATTRIBUTE)
    #define EXPORT_SYMBOL __attribute__ ((visibility ("default")))
  #endif
#elif defined(MSC_VER) && !defined(STATIC_LIBKOYOTECOINCONSENSUS)
  #define EXPORT_SYMBOL __declspec(dllimport)
#endif

#ifndef EXPORT_SYMBOL
  #define EXPORT_SYMBOL
#endif

#ifdef __cplusplus
extern "C" {
#endif

#define KOYOTECOINCONSENSUS_API_VER 1

typedef enum koyotecoinconsensus_error_t
{
    koyotecoinconsensus_ERR_OK = 0,
    koyotecoinconsensus_ERR_TX_INDEX,
    koyotecoinconsensus_ERR_TX_SIZE_MISMATCH,
    koyotecoinconsensus_ERR_TX_DESERIALIZE,
    koyotecoinconsensus_ERR_AMOUNT_REQUIRED,
    koyotecoinconsensus_ERR_INVALID_FLAGS,
} koyotecoinconsensus_error;

/** Script verification flags */
enum
{
    koyotecoinconsensus_SCRIPT_FLAGS_VERIFY_NONE                = 0,
    koyotecoinconsensus_SCRIPT_FLAGS_VERIFY_P2SH                = (1U << 0), // evaluate P2SH (BIP16) subscripts
    koyotecoinconsensus_SCRIPT_FLAGS_VERIFY_DERSIG              = (1U << 2), // enforce strict DER (BIP66) compliance
    koyotecoinconsensus_SCRIPT_FLAGS_VERIFY_NULLDUMMY           = (1U << 4), // enforce NULLDUMMY (BIP147)
    koyotecoinconsensus_SCRIPT_FLAGS_VERIFY_CHECKLOCKTIMEVERIFY = (1U << 9), // enable CHECKLOCKTIMEVERIFY (BIP65)
    koyotecoinconsensus_SCRIPT_FLAGS_VERIFY_CHECKSEQUENCEVERIFY = (1U << 10), // enable CHECKSEQUENCEVERIFY (BIP112)
    koyotecoinconsensus_SCRIPT_FLAGS_VERIFY_WITNESS             = (1U << 11), // enable WITNESS (BIP141)
    koyotecoinconsensus_SCRIPT_FLAGS_VERIFY_ALL                 = koyotecoinconsensus_SCRIPT_FLAGS_VERIFY_P2SH | koyotecoinconsensus_SCRIPT_FLAGS_VERIFY_DERSIG |
                                                               koyotecoinconsensus_SCRIPT_FLAGS_VERIFY_NULLDUMMY | koyotecoinconsensus_SCRIPT_FLAGS_VERIFY_CHECKLOCKTIMEVERIFY |
                                                               koyotecoinconsensus_SCRIPT_FLAGS_VERIFY_CHECKSEQUENCEVERIFY | koyotecoinconsensus_SCRIPT_FLAGS_VERIFY_WITNESS
};

/// Returns 1 if the input nIn of the serialized transaction pointed to by
/// txTo correctly spends the scriptPubKey pointed to by scriptPubKey under
/// the additional constraints specified by flags.
/// If not nullptr, err will contain an error/success code for the operation
EXPORT_SYMBOL int koyotecoinconsensus_verify_script(const unsigned char *scriptPubKey, unsigned int scriptPubKeyLen,
                                                 const unsigned char *txTo        , unsigned int txToLen,
                                                 unsigned int nIn, unsigned int flags, koyotecoinconsensus_error* err);

EXPORT_SYMBOL int koyotecoinconsensus_verify_script_with_amount(const unsigned char *scriptPubKey, unsigned int scriptPubKeyLen, int64_t amount,
                                    const unsigned char *txTo        , unsigned int txToLen,
                                    unsigned int nIn, unsigned int flags, koyotecoinconsensus_error* err);

EXPORT_SYMBOL unsigned int koyotecoinconsensus_version();

#ifdef __cplusplus
} // extern "C"
#endif

#undef EXPORT_SYMBOL

#endif // KOYOTECOIN_SCRIPT_KOYOTECOINCONSENSUS_H
