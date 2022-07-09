SERVICE := ghost
DESTDIR ?= dist_root
SERVICEDIR ?= /srv/$(SERVICE)

.PHONY: build install

build:
	#$(MAKE) -C src
	cd src && python3 build.py

nobin:
	cd src && python3 build.py nobin

install: build
#	cp src/helloworld $(DESTDIR)$(SERVICEDIR)/
#	mkdir -p $(DESTDIR)/etc/systemd/system
#	cp src/template@.service $(DESTDIR)/etc/systemd/system/
#	cp src/template.socket $(DESTDIR)/etc/systemd/system/
#	cp src/system-template.slice $(DESTDIR)/etc/systemd/system/
#	cp files/logrotate.timer $(DESTDIR)/usr/lib/systemd/system/
#	cp files/marty.conf $(DESTDIR)/etc/logrotate.d/
	mkdir -p $(DESTDIR)/srv
	mkdir -p $(DESTDIR)/etc/systemd/system
	cp src/setup $(DESTDIR)/srv/setup
	cp files/setup.service $(DESTDIR)/etc/systemd/system/setup.service
