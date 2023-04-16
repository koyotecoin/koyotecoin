// Copyright (c) 2021 The Bitcoin Core developers
// Copyright (c) 2023-2023 The Koyotecoin Core developers
// Distributed under the MIT software license, see the accompanying
// file COPYING or http://www.opensource.org/licenses/mit-license.php.

#ifndef KOYOTECOIN_IPC_CAPNP_PROTOCOL_H
#define KOYOTECOIN_IPC_CAPNP_PROTOCOL_H

#include <memory>

namespace ipc {
class Protocol;
namespace capnp {
std::unique_ptr<Protocol> MakeCapnpProtocol();
} // namespace capnp
} // namespace ipc

#endif // KOYOTECOIN_IPC_CAPNP_PROTOCOL_H
