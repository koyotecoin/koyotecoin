// Copyright (c) 2011-2020 The Bitcoin Core developers
// Copyright (c) 2023-2023 The Koyotecoin Core developers
// Distributed under the MIT software license, see the accompanying
// file COPYING or http://www.opensource.org/licenses/mit-license.php.

#ifndef KOYOTECOIN_QT_KOYOTECOINADDRESSVALIDATOR_H
#define KOYOTECOIN_QT_KOYOTECOINADDRESSVALIDATOR_H

#include <QValidator>

/** Base58 entry widget validator, checks for valid characters and
 * removes some whitespace.
 */
class KoyotecoinAddressEntryValidator : public QValidator
{
    Q_OBJECT

public:
    explicit KoyotecoinAddressEntryValidator(QObject *parent);

    State validate(QString &input, int &pos) const override;
};

/** Koyotecoin address widget validator, checks for a valid koyotecoin address.
 */
class KoyotecoinAddressCheckValidator : public QValidator
{
    Q_OBJECT

public:
    explicit KoyotecoinAddressCheckValidator(QObject *parent);

    State validate(QString &input, int &pos) const override;
};

#endif // KOYOTECOIN_QT_KOYOTECOINADDRESSVALIDATOR_H
