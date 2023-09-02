// Copyright (c) 2011-2020 The Bitcoin Core developers
// Copyright (c) 2023-2023 The Koyotecoin Core developers
// Distributed under the MIT software license, see the accompanying
// file COPYING or http://www.opensource.org/licenses/mit-license.php.

#ifndef KOYOTECOIN_QT_PSKTOPERATIONSDIALOG_H
#define KOYOTECOIN_QT_PSKTOPERATIONSDIALOG_H

#include <QDialog>

#include <pskt.h>
#include <qt/clientmodel.h>
#include <qt/walletmodel.h>

namespace Ui {
class PSKTOperationsDialog;
}

/** Dialog showing transaction details. */
class PSKTOperationsDialog : public QDialog
{
    Q_OBJECT

public:
    explicit PSKTOperationsDialog(QWidget* parent, WalletModel* walletModel, ClientModel* clientModel);
    ~PSKTOperationsDialog();

    void openWithPSKT(PartiallySignedTransaction psktx);

public Q_SLOTS:
    void signTransaction();
    void broadcastTransaction();
    void copyToClipboard();
    void saveTransaction();

private:
    Ui::PSKTOperationsDialog* m_ui;
    PartiallySignedTransaction m_transaction_data;
    WalletModel* m_wallet_model;
    ClientModel* m_client_model;

    enum class StatusLevel {
        INFO,
        WARN,
        ERR
    };

    size_t couldSignInputs(const PartiallySignedTransaction &psktx);
    void updateTransactionDisplay();
    std::string renderTransaction(const PartiallySignedTransaction &psktx);
    void showStatus(const QString &msg, StatusLevel level);
    void showTransactionStatus(const PartiallySignedTransaction &psktx);
};

#endif // KOYOTECOIN_QT_PSKTOPERATIONSDIALOG_H
