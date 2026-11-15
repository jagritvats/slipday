#!/bin/sh
# Downloads every official file Slipday uses into data/reference/ (git-ignored, about 1.2 GB).
# Run from the repository root, on Linux, macOS or Git Bash on Windows:
#
#     sh scripts/fetch_on_your_machine.sh
#
# Run on 14 Nov 2026 from a Windows machine (Git Bash): every address below answered and every recorded
# hash matched.  Two things were fixed after the first, untested version of this script:
#   - pgda.gsfc.nasa.gov answers HTTP 200 with a "Not Found" web page for a wrong path, so `curl -f` does not
#     catch it; get() now refuses a download that starts like a web page.
#   - the Sun-map GeoTIFFs live under /data/MoonIllumination/, not /data/LOLA_illumination/.
# It fetches:
#   1. the LOLA team's Earth-visibility maps (the Earth check in scripts/validate_more.py) and the labels of
#      the Sun maps
#   2. the Sun-visibility maps the stored validation is run against
#   3. the four elevation products: the 80 m mosaic (PGDA), LDEM_75S_240M and LDEM_16 (PDS Geosciences) and
#      the 64 px/deg grid of NASA SVS's CGI Moon Kit (531 MB; scripts/prepare_dem.py crops it to 60S-90S)
# Then: python3 scripts/prepare_dem.py data/reference   (see LOCAL_PASS.md)
set -u
DEST=data/reference
mkdir -p "$DEST" && cd "$DEST" || exit 1
UA="slipday-fetch/1.0"
FAILED=""
get() { # get <file name to save as> <url> [more urls]
  f="$1"; shift
  [ -s "$f" ] && { echo "have $f"; return 0; }
  for u in "$@"; do
    # A long transfer can be cut by the server (seen once on 14 Nov 2026: curl error 56 at pgda.gsfc.nasa.gov).
    # Attempts 1 to 4 resume the partial file; the last one starts again from nothing.
    for attempt in 1 2 3 4 5; do
      [ "$attempt" = 5 ] && rm -f "$f.part"
      if curl -fL -A "$UA" --retry 3 -C - -o "$f.part" "$u"; then
        if head -c 200 "$f.part" | grep -qi "<!DOCTYPE html\|<html"; then
          echo "not a data file (the server sent a web page): $u"; break
        fi
        mv "$f.part" "$f"; echo "got  $f  <- $u  ($(wc -c < "$f" | tr -d ' ') bytes)"; return 0
      fi
      echo "interrupted (attempt $attempt of 5): $u"; sleep 3
    done
    rm -f "$f.part"
  done
  FAILED="$FAILED $f"; echo "FAILED $f"; return 1
}
check() { # check <file> <sha256>
  [ -s "$1" ] || return 0
  if command -v sha256sum >/dev/null 2>&1; then got=$(sha256sum "$1" | cut -d' ' -f1 | tr -d '\\'); else got=$(shasum -a 256 "$1" | cut -d' ' -f1); fi
  [ "$got" = "$2" ] && echo "hash ok   $1" || echo "hash DIFFERS for $1 (another product version?): $got"
}

IMB=https://imbrium.mit.edu/EXTRAS/ILLUMINATION
PGDA=https://pgda.gsfc.nasa.gov/data
PDS=https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/lrolol_1xxx/data/lola_gdr

# 1. Earth-visibility maps (LOLA team; same grids as the Sun maps), with their PDS labels, and the labels
#    of the Sun maps.  Listing: https://imbrium.mit.edu/EXTRAS/ILLUMINATION/IMG/ ; GeoTIFF versions are
#    linked from https://pgda.gsfc.nasa.gov/products/69 (under /data/MoonIllumination/).
for p in 85S_060M 75S_120M 65S_240M; do
  n=AVGVISIB_${p}_201608
  get ${n}_EARTH.IMG $IMB/IMG/${n}_EARTH.IMG
  get ${n}_EARTH.LBL $IMB/IMG/${n}_EARTH.LBL
  get ${n}.LBL $IMB/IMG/${n}.LBL
done
get README_ILLUMINATION_2016.TXT $IMB/README_ILLUMINATION_2016.TXT
check AVGVISIB_85S_060M_201608_EARTH.IMG 0958313069d6039b2474c875ff662f28dbcba2bd853d9ea458aa807b7948c11f
check AVGVISIB_75S_120M_201608_EARTH.IMG 443ad251a480dea19e96417dfcfe1cb87a91eb02ee158b262d78abe899258fff
check AVGVISIB_65S_240M_201608_EARTH.IMG b194b9a1ce0dacdb00dbdc546b99850656c206ba0e13956178831f72cc65d73e

# 2. Sun-visibility maps used by the stored validation, and the 240 m map as JPEG2000 with its label
#    (tests/test_round3.py exercises the JPEG2000 and IMG readers with it).
get AVGVISIB_85S_060M_201608.TIF $PGDA/MoonIllumination/AVGVISIB_85S_060M_201608.TIF
get AVGVISIB_75S_120M_201608.TIF $PGDA/MoonIllumination/AVGVISIB_75S_120M_201608.TIF
check AVGVISIB_85S_060M_201608.TIF ccf67d4f39e0a970c111196da7d6551ffcf50d075470b93067fb3904c0b05806
check AVGVISIB_75S_120M_201608.TIF d539467f16ccc5f51b6a904af6be5d16c9b2f194afe619b9f1f81841d9fec0bb
get AVGVISIB_65S_240M_201608.JP2 $IMB/JP2/AVGVISIB_65S_240M_201608.JP2
get AVGVISIB_65S_240M_201608_JP2.LBL $IMB/JP2/AVGVISIB_65S_240M_201608_JP2.LBL
check AVGVISIB_65S_240M_201608.JP2 4ccaf5ef7cdfc35bbff4d28e0d9b1051d9d56a66181cda633e71bfd42237dd49

# 3. Elevation products from their official hosts.
get LDEM_80S_80MPP_ADJ.TIF $PGDA/LOLA_20mpp/LDEM_80S_80MPP_ADJ.TIF
check LDEM_80S_80MPP_ADJ.TIF 82030dcbdd7c4bb0c7d858e9b4b293b9f2cda5a543ba31ec0f42784bd6beee5a
get LDEM_75S_240M.JP2 $PDS/polar/jp2/ldem_75s_240m.jp2
get LDEM_75S_240M_JP2.LBL $PDS/polar/jp2/ldem_75s_240m_jp2.lbl
check LDEM_75S_240M.JP2 a0ebbad0a2650c742ed2d4ec1314aa095f869ba800f817b1b72eeb9194345c36
get LDEM_16.IMG $PDS/cylindrical/img/ldem_16.img
get LDEM_16.LBL $PDS/cylindrical/img/ldem_16.lbl
check LDEM_16.IMG a511e40d7a3ea3275945b4da2a1df377133264fab0be94b7434b1cf8907254cb
get ldem_64_uint.tif https://svs.gsfc.nasa.gov/vis/a000000/a004700/a004720/ldem_64_uint.tif
check ldem_64_uint.tif 0f40bce8b42864deddb6943a38474879e691d5b20647aa5e54c2612b23106499

echo
[ -z "$FAILED" ] && echo "all files present in $DEST" || echo "not downloaded:$FAILED  (open https://pgda.gsfc.nasa.gov/products/69 and https://imbrium.mit.edu/EXTRAS/ILLUMINATION/ in a browser, save the files under the names above into $DEST)"
echo "next: python3 scripts/prepare_dem.py $DEST && python3 scripts/validate_more.py $DEST --only e      (see LOCAL_PASS.md)"
