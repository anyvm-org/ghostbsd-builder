# Runs inside the installed GhostBSD system over ssh, AFTER the post-install pkg
# step and just before the build VM is shut down and the image is exported. This
# is where we flip the image from the headless, text-login state the build needs
# (see conf/pcinstall.cfg and hooks/postBuild.sh, which keep a text "login:" so
# the builder's waitForText can detect boot) into a desktop image: the final
# exported image boots straight into the GhostBSD desktop.
#
# Three things are required for the desktop to come up under the anyvm VM (which
# uses a plain "vga" video device):
#   1. Remove GhostBSD's shipped spiceqxl Xorg config. It forces the "spiceqxl"
#      driver (meant for running Xorg as a SPICE server), which fatally fails to
#      load on a normal VM ("Failed to load module xspicekeyboard/xspicepointer",
#      Fatal server error). With it gone, Xorg auto-detects the vesa driver on the
#      vga device and the desktop renders.
#   2. Enable the lightdm display manager (the build disabled it).
#   3. Configure passwordless autologin for the build's "anyvm" user so the image
#      boots directly to the desktop instead of stopping at the login greeter.
echo '=================== finalize: enable desktop ===='

# 1) Drop the broken spiceqxl Xorg config (and any forced xorg.conf).
rm -f /usr/local/etc/X11/xorg.conf.d/spiceqxl.xorg.conf \
      /usr/local/etc/X11/xorg.conf \
      /etc/X11/xorg.conf

# 2) Enable lightdm (+ dbus). Strip any earlier lightdm_enable=NO lines the build
#    added so the effective value is unambiguous.
sed -i '' -E '/^[[:space:]]*lightdm_enable=/d' /etc/rc.conf 2>/dev/null || true
sysrc lightdm_enable="YES"
sysrc dbus_enable="YES"

# 3) Passwordless autologin for "anyvm" into the edition's default session
#    (user-session is already set per edition: mate / xfce / gershwin). Inject the
#    autologin keys under [Seat:*] only if they are not configured yet.
_ld=/usr/local/etc/lightdm/lightdm.conf
if [ -f "$_ld" ] && ! grep -qE '^[[:space:]]*autologin-user=anyvm' "$_ld"; then
  awk '
    { print }
    /^\[Seat:\*\]/ && !seen {
      print "autologin-user=anyvm"
      print "autologin-user-timeout=0"
      seen = 1
    }
  ' "$_ld" > "$_ld.tmp" && mv "$_ld.tmp" "$_ld"
fi

echo "finalize: desktop enabled (lightdm + autologin=anyvm, spiceqxl removed)."
