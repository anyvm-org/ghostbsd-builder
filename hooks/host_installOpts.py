# Unattended install driver for GhostBSD.
#
# GhostBSD only ships a live GUI installer (gbi), which is a front-end for the
# scriptable pc-sysinstall backend. There is no downloadable VM disk image, so we
# boot the live ISO, reach a root shell on the live system via the text console,
# and run pc-sysinstall directly with our own answer file (conf/pcinstall.cfg) --
# exactly the command gbi itself runs:
#
#     sudo /usr/local/sbin/pc-sysinstall -c <cfg>
#
# Host-side hook: run by base-builder/build.py via exec() in this module's
# globals, so waitForText / string / enter / inputKeys / vncKey / sleep / log /
# env / subprocess are all available as bare names.
#
# IMPORTANT: the screen-driving timings and the live-console login below are
# the parts most likely to need empirical tuning in CI -- this is the place to
# tune them.

# Under raw QEMU + slirp the guest always reaches the build host at
# 192.168.122.1 (build.py pins `host=` in -netdev user). The old libvirt-era
# network probe is gone.
_cfg_url = "http://192.168.122.1:8000/conf/pcinstall.cfg"

def _must_see(text, sec, what):
    # Every wait on the single-user path is bounded AND fatal: typing the next
    # command into a screen that never reached the expected state only moves
    # the failure somewhere unrelated.
    if waitForText(text, sec) != 0:
        log("FATAL: ghostbsd installOpts: %s (no '%s' within %s s)"
            % (what, text, sec))
        sys.exit(1)


if env("VM_LIVE_SINGLE_USER"):
    ########################################################################
    # 1) (26.2+) Reach a text-console login prompt by booting single-user.
    #
    #    From 26.2 the live media's rc starts the new GUI installer itself:
    #    /usr/local/etc/rc.d/install_station runs `startx -- :0 vt09` as
    #    root and blocks until install-station exits, so /etc/rc never
    #    finishes, init never spawns a getty, and the X server refuses VT
    #    switches -- the Ctrl+Alt+F2 trick of the branch below types into
    #    the installer window instead. (install_station_enable="YES" lives
    #    in /etc/rc.conf.d/install_station, which load_rc_config reads AFTER
    #    rc.conf, so an rc.conf override alone does not win.)
    #
    #    The way around it is to edit the live root before it boots:
    #    a) The loader menu is hidden (loader_menu_hidden=YES) behind a 2 s
    #       autoboot; any key other than Enter reveals it and cancels the
    #       countdown. Space is not a menu shortcut, so it is safe to send
    #       repeatedly until the menu shows. Send it through the QEMU
    #       monitor -- a vncdotool process per key is too slow to reliably
    #       land inside a 2 s window. This hook only starts ~3 s after QEMU
    #       does, which already missed the window once, so own the timing:
    #       system_reset first and start the keys right after it, retrying
    #       with a fresh reset if the menu still does not show.
    #    b) "s" = Boot Single user. The ramdisk's /init.sh then stops BEFORE
    #       replicating the live system and offers a shell on the ramdisk.
    #    c) Do the replication init.sh would have done (same commands, same
    #       memdisk size rule), which leaves the live pool mounted.
    #    d) Disable install_station, initial_setup and lightdm through
    #       rc.conf.d files (they win over rc.conf).
    #    e) Run the ramdisk's /etc/rc, which reroots into the live pool and
    #       boots it multi-user -- rc now completes and ttyv0 shows a getty.
    #    The markers are typed with an empty "" inside them so the echoed
    #    command line itself never matches the marker.
    ########################################################################
    _menu_found = False
    for _menu_try in range(1, 4):
        log("Revealing the hidden GhostBSD loader menu (attempt %d/3)..."
            % _menu_try)
        _menu_stop = threading.Event()

        def _menu_spam():
            while not _menu_stop.is_set():
                qmon("sendkey spc", timeout=0.2)
                time.sleep(0.3)

        # Short timeout: the default 2 s reply wait would itself eat the
        # autoboot window before the first key goes out.
        qmon("system_reset", timeout=0.2)
        _menu_thread = threading.Thread(target=_menu_spam, daemon=True)
        _menu_thread.start()
        try:
            _menu_found = (waitForText("Single", "90") == 0)
        finally:
            _menu_stop.set()
            _menu_thread.join()
        if _menu_found:
            break
    if not _menu_found:
        log("FATAL: ghostbsd installOpts: loader menu never appeared "
            "(no 'Single' after 3 resets)")
        sys.exit(1)
    qmon("sendkey s")
    # The prompt is "Enter full pathname of shell or RETURN for /rescue/sh:".
    # OCR has dropped the last letter of "pathname" in CI, so anchor on the
    # all-caps RETURN, which only appears on this prompt.
    _must_see("RETURN", "600", "single-user ramdisk shell never offered")
    enter()
    time.sleep(3)

    string("mdconfig -a -t swap -s $(( $(sysctl -n hw.realmem) * 75 / 100 "
           "/ 1073741824 ))g -u 1 && zpool create -O primarycache=none "
           "livecd /dev/md1 && zfs set compression=zstd-9 livecd && "
           "dd if=/cdrom/data/system.img bs=1M | zfs recv -F livecd && "
           "echo REPLI\"\"CATED")
    enter()
    # Match a prefix of the marker, not all of it: OCR has already dropped a
    # trailing letter once (see RETURN above).
    _must_see("REPLICA", "1800", "live system replication failed")

    string("R=\"$(zfs get -H -o value mountpoint livecd)\"; "
           "mkdir -p \"$R/etc/rc.conf.d\" && "
           "for s in install_station initial_setup lightdm; do "
           "echo \"${s}_enable=NO\" > \"$R/etc/rc.conf.d/$s\"; done && "
           "echo PAT\"\"CHED")
    enter()
    _must_see("PATCHE", "120", "could not disable the live GUI installer")

    string("/rescue/sh /etc/rc")
    enter()
    log("Rerooting into the live system; waiting for the ttyv0 login prompt...")
    _must_see("logi", "900", "live system never reached a login prompt")
else:
    ########################################################################
    # 1) Reach a text-console login prompt.
    #
    #    The GhostBSD live ISO copies itself into a swap-backed memdisk and
    #    REROOTS before the login getty appears. On a slow/contended host
    #    that copy can take the better part of an hour, so a single early
    #    Ctrl+Alt+F2 is lost across the reroot. Re-issue Ctrl+Alt+F2 on
    #    every poll via the waitForText hook so the switch to ttyv1 is
    #    re-asserted until the getty prompt actually appears -- regardless
    #    of how long the boot takes. OCR renders the live media's "login:"
    #    consistently as "logi".
    ########################################################################
    log("Waiting for the GhostBSD live system to boot and reach a login prompt...")
    time.sleep(60)
    vncKey("ctrl-alt-f2")
    waitForText("logi", "400", hook=lambda: vncKey("ctrl-alt-f2"))

############################################################################
# 2) Log in. On the GhostBSD live media root logs in on the console with no
#    password. If that ever changes, this is the spot to add a password.
############################################################################
string("root")
enter()
time.sleep(5)
# Harmless extra Enter in case an (empty) password prompt is shown.
enter()
time.sleep(15)

############################################################################
# 3) Fetch our answer file from the build host and run pc-sysinstall, then
#    power the VM off so build.py proceeds. We go through sudo so the same
#    line works whether the live login is root or the live user (gbi relies
#    on passwordless sudo on the live media). The fetch is issued twice (it
#    is idempotent) to ride out a transient hiccup just after the live
#    network comes up.
############################################################################
string("sudo fetch -o /tmp/pcinstall.cfg %s" % _cfg_url)
enter()
time.sleep(12)
string("sudo fetch -o /tmp/pcinstall.cfg %s" % _cfg_url)
enter()
time.sleep(8)
# Show the config in the build log for debugging.
string("cat /tmp/pcinstall.cfg")
enter()
time.sleep(3)

string("sudo /usr/local/sbin/pc-sysinstall -c /tmp/pcinstall.cfg")
enter()

# Give pc-sysinstall time to partition, create the pool and clone the live
# filesystem to disk. build.py waits for the VM to power off after this hook
# returns, so block here until the install is plausibly done.
# pc-sysinstall prints "Installation finished!" on success (OCR sees the "!"
# as "?"), so match the OCR-robust substring "finished".
log("Running pc-sysinstall; waiting for it to finish...")
waitForText("finished", "1200")

time.sleep(10)
string("sudo shutdown -p now")
enter()
