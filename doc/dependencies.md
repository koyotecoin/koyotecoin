# Dependencies

These are the dependencies used by Koyotecoin Core.
You can find installation instructions in the `build-*.md` file for your platform.
"Runtime" and "Version Used" are both in reference to the release binaries.

| Dependency | Minimum required |
| --- | --- |
| [Autoconf](https://www.gnu.org/software/autoconf/) | [2.69] |
| [Automake](https://www.gnu.org/software/automake/) | [1.13] |
| [Clang](https://clang.llvm.org) | [8.0] |
| [GCC](https://gcc.gnu.org) | [8.1] |
| [Python](https://www.python.org) (tests) | [3.6] |
| [systemtap](https://sourceware.org/systemtap/) ([tracing](tracing.md))| N/A |

## Required

| Dependency | Releases | Version used | Minimum required | Runtime |
| --- | --- | --- | --- | --- |
| [Boost](../depends/packages/boost.mk) | [link](https://www.boost.org/users/download/) | [1.77.0] | [1.64.0] | No |
| [libevent](../depends/packages/libevent.mk) | [link](https://github.com/libevent/libevent/releases) | [2.1.12-stable] | [2.1.8] | No |
| glibc | [link](https://www.gnu.org/software/libc/) | N/A | [2.18] | Yes |
| Linux Kernel | [link](https://www.kernel.org/) | N/A | 3.2.0 | Yes |

## Optional

### GUI
| Dependency | Releases | Version used | Minimum required | Runtime |
| --- | --- | --- | --- | --- |
| [Fontconfig](../depends/packages/fontconfig.mk) | [link](https://www.freedesktop.org/wiki/Software/fontconfig/) | [2.12.6] | 2.6 | Yes |
| [FreeType](../depends/packages/freetype.mk) | [link](https://freetype.org) | [2.11.0] | 2.3.0 | Yes |
| [qrencode](../depends/packages/qrencode.mk) | [link](https://fukuchi.org/works/qrencode/) | [3.4.4] | | No |
| [Qt](../depends/packages/qt.mk) | [link](https://download.qt.io/official_releases/qt/) | [5.15.5] | [5.11.3] | No |

### Networking
| Dependency | Releases | Version used | Minimum required | Runtime |
| --- | --- | --- | --- | --- |
| [libnatpmp](../depends/packages/libnatpmp.mk) | [link](https://github.com/miniupnp/libnatpmp/) | | No |
| [MiniUPnPc](../depends/packages/miniupnpc.mk) | [link](https://miniupnp.tuxfamily.org/) | [2.2.2] | 1.9 | No |

### Notifications
| Dependency | Releases | Version used | Minimum required | Runtime |
| --- | --- | --- | --- | --- |
| [ZeroMQ](../depends/packages/zeromq.mk) | [link](https://github.com/zeromq/libzmq/releases) | [4.3.4] | 4.0.0 | No |

### Wallet
| Dependency | Releases | Version used | Minimum required | Runtime |
| --- | --- | --- | --- | --- |
| [Berkeley DB](../depends/packages/bdb.mk) (legacy wallet) | [link](https://www.oracle.com/technetwork/database/database-technologies/berkeleydb/downloads/index.html) | 4.8.30 | 4.8.x | No |
| [SQLite](../depends/packages/sqlite.mk) | [link](https://sqlite.org) | [3.32.1] | [3.7.17] | No |
