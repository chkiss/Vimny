# Homebrew formula for Vimny.
#
# This file does not live here to be used from here — Homebrew reads formulae
# out of a TAP repository. Copy it to `homebrew-tap/Formula/vimny.rb` in a repo
# named `chkiss/homebrew-tap` and users get:
#
#     brew install chkiss/tap/vimny
#
# Why a tap rather than a signed .app: brew builds on the user's machine, so
# there is no Developer ID, no notarization, and no Gatekeeper prompt. See
# packaging/README.md for the release runbook and how to refresh the hashes.

class Vimny < Formula
  include Language::Python::Virtualenv

  desc "Dungeon crawler that teaches Vim through play"
  homepage "https://github.com/chkiss/Vimny"
  # TODO(release): fill both in from PyPI once `vimny` is published — see
  # packaging/README.md. Until then this formula cannot be installed.
  url "https://files.pythonhosted.org/packages/source/v/vimny/vimny-1.0.0.tar.gz"
  sha256 "0000000000000000000000000000000000000000000000000000000000000000"
  license "GPL-3.0-or-later"

  depends_on "python@3.12"

  # Vendored dependencies. Keep these at the versions pip would resolve — see
  # `brew update-python-resources vimny` to regenerate them after a release.
  resource "blessed" do
    url "https://files.pythonhosted.org/packages/82/45/ad23d265373cdb7f255d2e3ed5f122b62914bd3c425bb21bca01ef699e5c/blessed-1.47.0.tar.gz"
    sha256 "ea13e06ae40f24710325411c5fa9b689d215cf170276cf1fda41feddaec8d3e0"
  end

  resource "wcwidth" do
    url "https://files.pythonhosted.org/packages/34/74/c6428f875774288bec1396f5bfcbc2d925700a4dad61727fd5f2b12f249d/wcwidth-0.8.2.tar.gz"
    sha256 "91fbef97204b96a3d4d421609b80340b760cf33e26da123ff243d76b1fda8dda"
  end

  resource "jinxed" do
    url "https://files.pythonhosted.org/packages/39/d7/6e6d474ec5eaeca6a61acc17766bb19563b3a372b4b9d92910078f5fe49f/jinxed-2.1.0.tar.gz"
    sha256 "7e755b831faa2443d44fb4ce7c0202eb9c3ed39bd5bf1193365888f4f6092b54"
  end

  def install
    virtualenv_install_with_resources
  end

  test do
    # Vimny is a full-screen TUI, so it cannot be launched under `brew test` —
    # there is no terminal to draw into. Check the console script exists and the
    # package imports and can build a dungeon, which exercises the real engine.
    assert_match "vimny", (bin/"vimny").read
    system libexec/"bin/python", "-c", <<~PYTHON
      import vimny.generation.dungeon_gen as dg
      room = dg.build_dungeon_character_cataracts(42).rooms[0]
      assert room.par > 0, "dungeon built with no par"
    PYTHON
  end
end
