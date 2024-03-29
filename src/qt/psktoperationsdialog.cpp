// Copyright (c) 2011-2021 The Bitcoin Core developers
// Copyright (c) 2023-2023 The Koyotecoin Core developers
// Distributed under the MIT software license, see the accompanying
// file COPYING or http://www.opensource.org/licenses/mit-license.php.

#include <qt/psktoperationsdialog.h>

#include <core_io.h>
#include <fs.h>
#include <interfaces/node.h>
#include <key_io.h>
#include <node/pskt.h>
#include <policy/policy.h>
#include <qt/koyotecoinunits.h>
#include <qt/forms/ui_psktoperationsdialog.h>
#include <qt/guiutil.h>
#include <qt/optionsmodel.h>
#include <util/strencodings.h>

#include <fstream>
#include <iostream>
#include <string>

using node::AnalyzePSKT;
using node::DEFAULT_MAX_RAW_TX_FEE_RATE;
using node::PSKTAnalysis;

PSKTOperationsDialog::PSKTOperationsDialog(
    QWidget* parent, WalletModel* wallet_model, ClientModel* client_model) : QDialog(parent, GUIUtil::dialog_flags),
                                                                             m_ui(new Ui::PSKTOperationsDialog),
                                                                             m_wallet_model(wallet_model),
                                                                             m_client_model(client_model)
{
    m_ui->setupUi(this);
    setWindowTitle("PSKT Operations");

    connect(m_ui->signTransactionButton, &QPushButton::clicked, this, &PSKTOperationsDialog::signTransaction);
    connect(m_ui->broadcastTransactionButton, &QPushButton::clicked, this, &PSKTOperationsDialog::broadcastTransaction);
    connect(m_ui->copyToClipboardButton, &QPushButton::clicked, this, &PSKTOperationsDialog::copyToClipboard);
    connect(m_ui->saveButton, &QPushButton::clicked, this, &PSKTOperationsDialog::saveTransaction);

    connect(m_ui->closeButton, &QPushButton::clicked, this, &PSKTOperationsDialog::close);

    m_ui->signTransactionButton->setEnabled(false);
    m_ui->broadcastTransactionButton->setEnabled(false);
}

PSKTOperationsDialog::~PSKTOperationsDialog()
{
    delete m_ui;
}

void PSKTOperationsDialog::openWithPSKT(PartiallySignedTransaction psktx)
{
    m_transaction_data = psktx;

    bool complete = FinalizePSKT(psktx); // Make sure all existing signatures are fully combined before checking for completeness.
    if (m_wallet_model) {
        size_t n_could_sign;
        TransactionError err = m_wallet_model->wallet().fillPSKT(SIGHASH_ALL, false /* sign */, true /* bip32derivs */, &n_could_sign, m_transaction_data, complete);
        if (err != TransactionError::OK) {
            showStatus(tr("Failed to load transaction: %1")
                           .arg(QString::fromStdString(TransactionErrorString(err).translated)),
                       StatusLevel::ERR);
            return;
        }
        m_ui->signTransactionButton->setEnabled(!complete && !m_wallet_model->wallet().privateKeysDisabled() && n_could_sign > 0);
    } else {
        m_ui->signTransactionButton->setEnabled(false);
    }

    m_ui->broadcastTransactionButton->setEnabled(complete);

    updateTransactionDisplay();
}

void PSKTOperationsDialog::signTransaction()
{
    bool complete;
    size_t n_signed;

    WalletModel::UnlockContext ctx(m_wallet_model->requestUnlock());

    TransactionError err = m_wallet_model->wallet().fillPSKT(SIGHASH_ALL, true /* sign */, true /* bip32derivs */, &n_signed, m_transaction_data, complete);

    if (err != TransactionError::OK) {
        showStatus(tr("Failed to sign transaction: %1")
            .arg(QString::fromStdString(TransactionErrorString(err).translated)), StatusLevel::ERR);
        return;
    }

    updateTransactionDisplay();

    if (!complete && !ctx.isValid()) {
        showStatus(tr("Cannot sign inputs while wallet is locked."), StatusLevel::WARN);
    } else if (!complete && n_signed < 1) {
        showStatus(tr("Could not sign any more inputs."), StatusLevel::WARN);
    } else if (!complete) {
        showStatus(tr("Signed %1 inputs, but more signatures are still required.").arg(n_signed),
            StatusLevel::INFO);
    } else {
        showStatus(tr("Signed transaction successfully. Transaction is ready to broadcast."),
            StatusLevel::INFO);
        m_ui->broadcastTransactionButton->setEnabled(true);
    }
}

void PSKTOperationsDialog::broadcastTransaction()
{
    CMutableTransaction mtx;
    if (!FinalizeAndExtractPSKT(m_transaction_data, mtx)) {
        // This is never expected to fail unless we were given a malformed PSKT
        // (e.g. with an invalid signature.)
        showStatus(tr("Unknown error processing transaction."), StatusLevel::ERR);
        return;
    }

    CTransactionRef tx = MakeTransactionRef(mtx);
    std::string err_string;
    TransactionError error =
        m_client_model->node().broadcastTransaction(tx, DEFAULT_MAX_RAW_TX_FEE_RATE.GetFeePerK(), err_string);

    if (error == TransactionError::OK) {
        showStatus(tr("Transaction broadcast successfully! Transaction ID: %1")
            .arg(QString::fromStdString(tx->GetHash().GetHex())), StatusLevel::INFO);
    } else {
        showStatus(tr("Transaction broadcast failed: %1")
            .arg(QString::fromStdString(TransactionErrorString(error).translated)), StatusLevel::ERR);
    }
}

void PSKTOperationsDialog::copyToClipboard() {
    CDataStream ssTx(SER_NETWORK, PROTOCOL_VERSION);
    ssTx << m_transaction_data;
    GUIUtil::setClipboard(EncodeBase64(ssTx.str()).c_str());
    showStatus(tr("PSKT copied to clipboard."), StatusLevel::INFO);
}

void PSKTOperationsDialog::saveTransaction() {
    CDataStream ssTx(SER_NETWORK, PROTOCOL_VERSION);
    ssTx << m_transaction_data;

    QString selected_filter;
    QString filename_suggestion = "";
    bool first = true;
    for (const CTxOut& out : m_transaction_data.tx->vout) {
        if (!first) {
            filename_suggestion.append("-");
        }
        CTxDestination address;
        ExtractDestination(out.scriptPubKey, address);
        QString amount = KoyotecoinUnits::format(m_client_model->getOptionsModel()->getDisplayUnit(), out.nValue);
        QString address_str = QString::fromStdString(EncodeDestination(address));
        filename_suggestion.append(address_str + "-" + amount);
        first = false;
    }
    filename_suggestion.append(".pskt");
    QString filename = GUIUtil::getSaveFileName(this,
        tr("Save Transaction Data"), filename_suggestion,
        //: Expanded name of the binary PSKT file format. See: BIP 174.
        tr("Partially Signed Transaction (Binary)") + QLatin1String(" (*.pskt)"), &selected_filter);
    if (filename.isEmpty()) {
        return;
    }
    std::ofstream out{filename.toLocal8Bit().data(), std::ofstream::out | std::ofstream::binary};
    out << ssTx.str();
    out.close();
    showStatus(tr("PSKT saved to disk."), StatusLevel::INFO);
}

void PSKTOperationsDialog::updateTransactionDisplay() {
    m_ui->transactionDescription->setText(QString::fromStdString(renderTransaction(m_transaction_data)));
    showTransactionStatus(m_transaction_data);
}

std::string PSKTOperationsDialog::renderTransaction(const PartiallySignedTransaction &psktx)
{
    QString tx_description = "";
    CAmount totalAmount = 0;
    for (const CTxOut& out : psktx.tx->vout) {
        CTxDestination address;
        ExtractDestination(out.scriptPubKey, address);
        totalAmount += out.nValue;
        tx_description.append(tr(" * Sends %1 to %2")
            .arg(KoyotecoinUnits::formatWithUnit(KoyotecoinUnit::KYC, out.nValue))
            .arg(QString::fromStdString(EncodeDestination(address))));
        tx_description.append("<br>");
    }

    PSKTAnalysis analysis = AnalyzePSKT(psktx);
    tx_description.append(" * ");
    if (!*analysis.fee) {
        // This happens if the transaction is missing input UTXO information.
        tx_description.append(tr("Unable to calculate transaction fee or total transaction amount."));
    } else {
        tx_description.append(tr("Pays transaction fee: "));
        tx_description.append(KoyotecoinUnits::formatWithUnit(KoyotecoinUnit::KYC, *analysis.fee));

        // add total amount in all subdivision units
        tx_description.append("<hr />");
        QStringList alternativeUnits;
        for (const KoyotecoinUnits::Unit u : KoyotecoinUnits::availableUnits())
        {
            if(u != m_client_model->getOptionsModel()->getDisplayUnit()) {
                alternativeUnits.append(KoyotecoinUnits::formatHtmlWithUnit(u, totalAmount));
            }
        }
        tx_description.append(QString("<b>%1</b>: <b>%2</b>").arg(tr("Total Amount"))
            .arg(KoyotecoinUnits::formatHtmlWithUnit(m_client_model->getOptionsModel()->getDisplayUnit(), totalAmount)));
        tx_description.append(QString("<br /><span style='font-size:10pt; font-weight:normal;'>(=%1)</span>")
            .arg(alternativeUnits.join(" " + tr("or") + " ")));
    }

    size_t num_unsigned = CountPSKTUnsignedInputs(psktx);
    if (num_unsigned > 0) {
        tx_description.append("<br><br>");
        tx_description.append(tr("Transaction has %1 unsigned inputs.").arg(QString::number(num_unsigned)));
    }

    return tx_description.toStdString();
}

void PSKTOperationsDialog::showStatus(const QString &msg, StatusLevel level) {
    m_ui->statusBar->setText(msg);
    switch (level) {
        case StatusLevel::INFO: {
            m_ui->statusBar->setStyleSheet("QLabel { background-color : lightgreen }");
            break;
        }
        case StatusLevel::WARN: {
            m_ui->statusBar->setStyleSheet("QLabel { background-color : orange }");
            break;
        }
        case StatusLevel::ERR: {
            m_ui->statusBar->setStyleSheet("QLabel { background-color : red }");
            break;
        }
    }
    m_ui->statusBar->show();
}

size_t PSKTOperationsDialog::couldSignInputs(const PartiallySignedTransaction &psktx) {
    if (!m_wallet_model) {
        return 0;
    }

    size_t n_signed;
    bool complete;
    TransactionError err = m_wallet_model->wallet().fillPSKT(SIGHASH_ALL, false /* sign */, false /* bip32derivs */, &n_signed, m_transaction_data, complete);

    if (err != TransactionError::OK) {
        return 0;
    }
    return n_signed;
}

void PSKTOperationsDialog::showTransactionStatus(const PartiallySignedTransaction &psktx) {
    PSKTAnalysis analysis = AnalyzePSKT(psktx);
    size_t n_could_sign = couldSignInputs(psktx);

    switch (analysis.next) {
        case PSKTRole::UPDATER: {
            showStatus(tr("Transaction is missing some information about inputs."), StatusLevel::WARN);
            break;
        }
        case PSKTRole::SIGNER: {
            QString need_sig_text = tr("Transaction still needs signature(s).");
            StatusLevel level = StatusLevel::INFO;
            if (!m_wallet_model) {
                need_sig_text += " " + tr("(But no wallet is loaded.)");
                level = StatusLevel::WARN;
            } else if (m_wallet_model->wallet().privateKeysDisabled()) {
                need_sig_text += " " + tr("(But this wallet cannot sign transactions.)");
                level = StatusLevel::WARN;
            } else if (n_could_sign < 1) {
                need_sig_text += " " + tr("(But this wallet does not have the right keys.)"); // XXX wording
                level = StatusLevel::WARN;
            }
            showStatus(need_sig_text, level);
            break;
        }
        case PSKTRole::FINALIZER:
        case PSKTRole::EXTRACTOR: {
            showStatus(tr("Transaction is fully signed and ready for broadcast."), StatusLevel::INFO);
            break;
        }
        default: {
            showStatus(tr("Transaction status is unknown."), StatusLevel::ERR);
            break;
        }
    }
}
