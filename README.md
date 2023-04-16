Koyotecoin Core integration/staging tree
=====================================

Koyotecoin is an open source censorship-resistant peer-to-peer immutable network for education, meme and fun.
https://koyotecoin.org

For an immediately usable, binary version of the Koyotecoin Core software, see
https://koyotecoin.org/download/.

What is Koyotecoin Core?
---------------------

Koyotecoin Core connects to the Koyotecoin peer-to-peer network to download and fully
validate blocks and transactions. It also includes a wallet and graphical user
interface, which can be optionally built.

Further information about Koyotecoin Core is available in the [doc folder](/doc).

License
-------

Koyotecoin Core is released under the terms of the MIT license. See [COPYING](COPYING) for more
information or see https://opensource.org/licenses/MIT.

Development Process
-------------------

The `master` branch is regularly built (see `doc/build-*.md` for instructions) and tested, but it is not guaranteed to be completely stable. [Tags](https://github.com/koyotecoin/koyotecoin/tags) are created regularly from release branches to indicate new official, stable release versions of Koyotecoin Core.

The contribution workflow is described in [CONTRIBUTING.md](CONTRIBUTING.md) and useful hints for developers can be found in [doc/developer-notes.md](doc/developer-notes.md).

Testing
-------

Testing and code review is the bottleneck for development; we get more pull requests than we can review and test on short notice. Please be patient and help out by testing other people's pull requests, and remember this is a security-critical project where any mistake might cost people lots of money.

### Automated Testing

Developers are strongly encouraged to write [unit tests](src/test/README.md) for new code, and to
submit new unit tests for old code. Unit tests can be compiled and run
(assuming they weren't disabled in configure) with: `make check`. Further details on running
and extending unit tests can be found in [/src/test/README.md](/src/test/README.md).

There are also [regression and integration tests](/test), written
in Python.
These tests can be run (if the [test dependencies](/test) are installed) with: `test/functional/test_runner.py`

The CI (Continuous Integration) systems make sure that every pull request is built for Windows, Linux, and macOS,
and that unit/sanity tests are run automatically.

### Manual Quality Assurance (QA) Testing

Changes should be tested by somebody other than the developer who wrote the code. This is especially important for large or high-risk changes. It is useful to add a test plan to the pull request description if testing the changes is not straightforward.

Translations
------------

Changes to translations as well as new translations can be submitted directly to Koyotecoin Core's GitHub repository by creating a pull request.

Translations will be periodically reviewed and merged into the git repository. See the [translation process](doc/translation_process.md) for details on how this works.

**Important**: Please make sure to update only the translation files and avoid making changes to the code or other non-related files.
