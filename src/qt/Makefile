.PHONY: FORCE
all: FORCE
	$(MAKE) -C .. koyotecoin_qt test_koyotecoin_qt
clean: FORCE
	$(MAKE) -C .. koyotecoin_qt_clean test_koyotecoin_qt_clean
check: FORCE
	$(MAKE) -C .. test_koyotecoin_qt_check
koyotecoin-qt koyotecoin-qt.exe: FORCE
	 $(MAKE) -C .. koyotecoin_qt
apk: FORCE
	$(MAKE) -C .. koyotecoin_qt_apk
