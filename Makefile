# Regenerate the profile art.
#
#   make          rebuild everything from the committed sources
#   make data     re-scrape the contribution calendar
#   make photo    redo the ASCII portrait from source-photo.jpg
#
# PALETTE switches the whole look: tokyo, mono, or hybrid (the default,
# a grey hero over a violet calendar). See scripts/palettes.py.

PALETTE ?= hybrid
PY      ?= python3
S        = scripts

# Head-and-shoulders box in source-photo.jpg, as left,top,right,bottom.
# Retune this if the photo is replaced.
CROP    ?= 320,426,880,946

.PHONY: all data art photo clean
all: art

data:
	$(PY) $(S)/fetch_contributions.py --user abdul-rehman174 --out data/contributions.json

# The calendar is the only piece the daily Action rebuilds; the rest change
# only when the photo or profile.json does.
art: data
	$(PY) $(S)/render_heatmap_svg.py --data data/contributions.json \
		--palette $(PALETTE) --out contrib-heatmap.svg \
		--title "abdul-rehman174 on GitHub"
	$(PY) $(S)/make_wordmark_svg.py --text AR --palette $(PALETTE) \
		--cell-w 29 --cell-h 48 --depth 3 --out wordmark.svg
	$(PY) $(S)/make_info_card.py --config profile.json \
		--palette $(PALETTE) --out info-card.svg
	$(PY) $(S)/make_ascii_svg.py --src source-prepped.png --palette $(PALETTE) \
		--cols 100 --out portrait-ascii.svg \
		--label "Abdul Rehman, in ASCII"

# Needs Pillow + numpy. Only run when the photo changes -- the prepped PNG
# is committed so the daily job never touches image libraries.
photo:
	$(PY) $(S)/prep_photo.py source-photo.jpg --crop $(CROP) \
		--out source-prepped.png --tol 14 --clip 1.6 --mix 0.45
	$(MAKE) art

clean:
	rm -f contrib-heatmap.svg wordmark.svg info-card.svg portrait-ascii.svg
