# English patch: the descriptions are 160x72, in the order the Court Record's
# sprites take them (tools/en/desc_tiles.py, court_record.c)
EVIDENCE_PROFILE_DESCRIPTIONS := graphics/evidence_profile_descriptions
$(EVIDENCE_PROFILE_DESCRIPTIONS)/%.4bpp: $(EVIDENCE_PROFILE_DESCRIPTIONS)/%.png tools/en/desc_tiles.py
	python3 tools/en/desc_tiles.py $< $@
$(EVIDENCE_PROFILE_DESCRIPTIONS)/%.4bpp.lz: $(EVIDENCE_PROFILE_DESCRIPTIONS)/%.4bpp
	$(GBAGFX) $< $@ -search 8

EVIDENCE_PROFILE_DESCRIPTIONS_EVIDENCE := graphics/evidence_profile_descriptions/evidence
$(EVIDENCE_PROFILE_DESCRIPTIONS_EVIDENCE)/%.4bpp: $(EVIDENCE_PROFILE_DESCRIPTIONS_EVIDENCE)/%.png tools/en/desc_tiles.py
	python3 tools/en/desc_tiles.py $< $@
$(EVIDENCE_PROFILE_DESCRIPTIONS_EVIDENCE)/%.4bpp.lz: $(EVIDENCE_PROFILE_DESCRIPTIONS_EVIDENCE)/%.4bpp
	$(GBAGFX) $< $@ -search 8

EVIDENCE_PROFILE_DESCRIPTIONS_PROFILES := graphics/evidence_profile_descriptions/profiles
$(EVIDENCE_PROFILE_DESCRIPTIONS_PROFILES)/%.4bpp: $(EVIDENCE_PROFILE_DESCRIPTIONS_PROFILES)/%.png tools/en/desc_tiles.py
	python3 tools/en/desc_tiles.py $< $@
$(EVIDENCE_PROFILE_DESCRIPTIONS_PROFILES)/%.4bpp.lz: $(EVIDENCE_PROFILE_DESCRIPTIONS_PROFILES)/%.4bpp
	$(GBAGFX) $< $@ -search 8

LOCATION_CHOICES := graphics/location_choices
TALK_CHOICES := graphics/talk_choices

$(LOCATION_CHOICES)/%.4bpp: $(LOCATION_CHOICES)/%.png
	$(GBAGFX) $< $@ -mwidth 8 -mheight 4

$(TALK_CHOICES)/%.4bpp: $(TALK_CHOICES)/%.png
	$(GBAGFX) $< $@ -mwidth 8 -mheight 4

# English patch: the Rise from the Ashes build's plates (tools/en/rfta/plates.py)
graphics/en/rfta/location_choices.4bpp graphics/en/rfta/talk_choices.4bpp graphics/en/rfta/episode_title.4bpp: %.4bpp: %.png
	$(GBAGFX) $< $@ -mwidth 8 -mheight 4
graphics/en/rfta/descriptions/%.4bpp: graphics/en/rfta/descriptions/%.png tools/en/desc_tiles.py
	python3 tools/en/desc_tiles.py $< $@
graphics/en/rfta/descriptions/%.4bpp.lz: graphics/en/rfta/descriptions/%.4bpp
	$(GBAGFX) $< $@ -search 8

graphics/title_screen.8bpp.lz: graphics/title_screen.8bpp
	$(GBAGFX) $< $@ -search 8
graphics/title_screen_demo.8bpp.lz: graphics/title_screen_demo.8bpp
	$(GBAGFX) $< $@ -search 8
graphics/ui/trial/unused_testimony_characters.4bpp: graphics/ui/trial/unused_testimony_characters.png
	$(GBAGFX) $< $@ -mwidth 2 -mheight 2
graphics/ui/trial/press_present_buttons.4bpp: graphics/ui/trial/press_present_buttons.png
	$(GBAGFX) $< $@ -mwidth 4 -mheight 2
graphics/ui/court_record/profiles_text.4bpp: graphics/ui/court_record/profiles_text.png
	$(GBAGFX) $< $@ -mwidth 4 -mheight 2
graphics/ui/court_record/evidence_text.4bpp: graphics/ui/court_record/evidence_text.png
	$(GBAGFX) $< $@ -mwidth 4 -mheight 2
graphics/ui/trial/game_over_text.4bpp: graphics/ui/trial/game_over_text.png
	$(GBAGFX) $< $@ -mwidth 8 -mheight 8
graphics/ui/new_game_continue.4bpp: graphics/ui/new_game_continue.png
	$(GBAGFX) $< $@ -mwidth 4 -mheight 2
graphics/episode_select_options.4bpp: graphics/episode_select_options.png
	$(GBAGFX) $< $@ -mwidth 8 -mheight 4
graphics/episode_select_options.4bpp.lz: graphics/episode_select_options.4bpp
	$(GBAGFX) $< $@ -search 1
graphics/from_save_or_beginning_options.4bpp: graphics/from_save_or_beginning_options.png
	$(GBAGFX) $< $@ -mwidth 8 -mheight 4
graphics/speedlines_first_and_last_columns.4bpp: graphics/speedlines_first_and_last_columns.png
	$(GBAGFX) $< $@ -mwidth 1 -mheight 20
graphics/charset.4bpp: graphics/charset.png
	$(GBAGFX) $< $@ -mwidth 2 -mheight 2

# English patch: the pages whose lines move a pixel or two so that none touch
# (vwf.c VwfLineStarts): every script's, the Rise from the Ashes ones' too
# when they are there (the RFTA build's common script has its own number)
graphics/vwf/page_moves.bin: tools/en/text_gaps.py tools/en/phscr.py graphics/vwf/font_glyphs.bin graphics/vwf/font_widths.bin graphics/vwf/font_advance.bin $(wildcard script_en/*.phscr) $(wildcard script_rfta/*.phscr)
	python3 tools/en/text_gaps.py $@ $(wildcard script_en/*.phscr) $(wildcard script_rfta/*.phscr)
