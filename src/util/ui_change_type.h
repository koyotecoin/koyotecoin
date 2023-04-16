// Copyright (c) 2012-2020 The Bitcoin Core developers
// Copyright (c) 2023-2023 The Koyotecoin Core developers
// Distributed under the MIT software license, see the accompanying
// file COPYING or http://www.opensource.org/licenses/mit-license.php.

#ifndef KOYOTECOIN_UTIL_UI_CHANGE_TYPE_H
#define KOYOTECOIN_UTIL_UI_CHANGE_TYPE_H

/** General change type (added, updated, removed). */
enum ChangeType {
    CT_NEW,
    CT_UPDATED,
    CT_DELETED
};

#endif // KOYOTECOIN_UTIL_UI_CHANGE_TYPE_H
