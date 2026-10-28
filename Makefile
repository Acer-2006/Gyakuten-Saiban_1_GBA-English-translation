AS := tools/binutils/bin/arm-none-eabi-as
CPP := $(CC) -E
LD := tools/binutils/bin/arm-none-eabi-ld
OBJCOPY := tools/binutils/bin/arm-none-eabi-objcopy
SHA1SUM := sha1sum -c
GBAFIX := tools/gbafix/gbafix
GBAGFX := tools/gbagfx/gbagfx
SCANINC := tools/scaninc/scaninc
PREPROC := tools/preproc/preproc
MID := tools/mid2agb/mid2agb

include config.mk

# English patch: `make RFTA=1` builds the optional Rise from the Ashes ROM
# (32 MB, pwaa1_rfta.gba): the fifth episode of the DS release
# (docs/rise_from_the_ashes.md). Its code is under #if RFTA and its data in
# data/rfta/ and the rfta_data section; the plain build doesn't change.
RFTA ?= 0
ifeq ($(RFTA),1)
BUILD_NAME := $(BUILD_NAME)_rfta
ROM_END := 0xA000000
else
ROM_END := 0x9000000
endif

# English patch: two more options, for the optional patches (README,
# "Optional patches"); each builds into a directory and a ROM of its own:
#   `make COURT=GS1`   the first game's courtroom (pictures and pans) in place
#                      of Gyakuten Saiban 3's (pwaa1_gs1court.gba)
#   `make JPVOICES=1`  the Japanese voices (Igiari!, Matta!, Kurae!) in place
#                      of the DS's English ones (pwaa1_jpvoices.gba)
# Both together: pwaa1_gs1court_jpvoices.gba.
COURT ?= GS3
JPVOICES ?= 0
ifeq ($(COURT),GS1)
BUILD_NAME := $(BUILD_NAME)_gs1court
else
ifneq ($(COURT),GS3)
$(error COURT is GS3 (the default) or GS1)
endif
endif
ifeq ($(JPVOICES),1)
BUILD_NAME := $(BUILD_NAME)_jpvoices
endif


TOOLDIRS := $(filter-out tools/ignore tools/agbcc tools/binutils tools/en,$(wildcard tools/*))
TOOLBASE = $(TOOLDIRS:tools/%=%)
TOOLS = $(foreach tool,$(TOOLBASE),tools/$(tool)/$(tool)$(EXE))


# Clear the default suffixes
.SUFFIXES:
# Don't delete intermediate files
.SECONDARY:
# Delete files that weren't built properly
.DELETE_ON_ERROR:
# Secondary expansion is required for dependency variables in object rules.
.SECONDEXPANSION:

.PHONY: rom compare realclean clean clean_rev1 rev1 compare_rev1 tools clean-tools check-scripts $(TOOLDIRS)

ROM := $(BUILD_NAME).gba
OBJ_DIR := build/$(BUILD_NAME)

C_SUBDIR = src
ASM_SUBDIR = asm
DATA_ASM_SUBDIR = data
RODATA_ASM_SUBDIR = rodata
MID_SUBDIR = sound/songs/midi

C_BUILDDIR = $(OBJ_DIR)/$(C_SUBDIR)
ASM_BUILDDIR = $(OBJ_DIR)/$(ASM_SUBDIR)
DATA_ASM_BUILDDIR = $(OBJ_DIR)/$(DATA_ASM_SUBDIR)
RODATA_ASM_BUILDDIR = $(OBJ_DIR)/$(RODATA_ASM_SUBDIR)
MID_BUILDDIR = $(OBJ_DIR)/$(MID_SUBDIR)

C_SRCS := $(wildcard $(C_SUBDIR)/*.c $(C_SUBDIR)/*/*.c $(C_SUBDIR)/*/*/*.c)
C_OBJS := $(patsubst $(C_SUBDIR)/%.c,$(C_BUILDDIR)/%.o,$(C_SRCS))

C_ASM_SRCS += $(wildcard $(C_SUBDIR)/*.s $(C_SUBDIR)/*/*.s $(C_SUBDIR)/*/*/*.s)
C_ASM_OBJS := $(patsubst $(C_SUBDIR)/%.s,$(C_BUILDDIR)/%.o,$(C_ASM_SRCS))

ASM_SRCS := $(wildcard $(ASM_SUBDIR)/*.s)
ASM_OBJS := $(patsubst $(ASM_SUBDIR)/%.s,$(ASM_BUILDDIR)/%.o,$(ASM_SRCS))

DATA_ASM_SRCS := $(wildcard $(DATA_ASM_SUBDIR)/*.s)
ifeq ($(RFTA),1)
DATA_ASM_SRCS += $(wildcard $(DATA_ASM_SUBDIR)/rfta/*.s)
endif
DATA_ASM_OBJS := $(patsubst $(DATA_ASM_SUBDIR)/%.s,$(DATA_ASM_BUILDDIR)/%.o,$(DATA_ASM_SRCS))

RODATA_ASM_SRCS := $(wildcard $(RODATA_ASM_SUBDIR)/*.s)
RODATA_ASM_OBJS := $(patsubst $(RODATA_ASM_SUBDIR)/%.s,$(RODATA_ASM_BUILDDIR)/%.o,$(RODATA_ASM_SRCS))

MID_SRCS := $(wildcard $(MID_SUBDIR)/*.mid)
MID_OBJS := $(patsubst $(MID_SUBDIR)/%.mid,$(MID_BUILDDIR)/%.o,$(MID_SRCS))

OBJS     := $(C_OBJS) $(C_ASM_OBJS) $(ASM_OBJS) $(DATA_ASM_OBJS) $(RODATA_ASM_OBJS) $(MID_OBJS)
OBJS_REL := $(patsubst $(OBJ_DIR)/%,%,$(OBJS))

SUBDIRS  := $(sort $(dir $(OBJS)))

$(shell mkdir -p $(SUBDIRS))

ASFLAGS := -mcpu=arm7tdmi -mthumb-interwork
ifeq ($(JPVOICES),1)
ASFLAGS += --defsym EN_JP_VOICES=1
endif
ifeq ($(RFTA),1)
ASFLAGS += --defsym RFTA=1
endif

CC1             := tools/agbcc/bin/old_agbcc
override CFLAGS += -mthumb-interwork -Wimplicit -Wparentheses -Werror -O2 -fhex-asm

CPPFLAGS := -I tools/agbcc -I tools/agbcc/include -iquote include -DREVISION=$(GAME_REVISION) -nostdinc
ifeq ($(RFTA),1)
CPPFLAGS += -DRFTA=1
endif
ifeq ($(COURT),GS1)
CPPFLAGS += -DEN_GS1_COURT=1
endif

ifeq ($(DINFO),1)
CFLAGS += -g
endif

NAME := pwaa1
ELF = $(ROM:.gba=.elf)
MAP = $(ROM:.gba=.map)
TITLE := GYAKUTEN_SAI
# English patch: a game code of its own (E: the English version). Tools that
# recognize a ROM by its code alone took this one for the Japanese game: the
# SuperCard's SuperFW firmware applied its patches for the Japanese ROM (wait
# state and save fixes at that ROM's code offsets), which land in the middle
# of other code here, and the game hung on a white screen. Under a code of
# its own the firmware generates patches for this ROM with its patch engine.
GAMECODE := ASBE

all: rom

tools: $(TOOLDIRS)

$(TOOLDIRS):
	@$(MAKE) -C $@

rom: $(ROM)
ifeq ($(COMPARE),1)
	@$(SHA1SUM) $(BUILD_NAME).sha1
endif

compare:
	@$(MAKE) COMPARE=1

realclean: clean clean-tools clean-assets

clean-tools:
	@$(foreach tooldir,$(TOOLDIRS),$(MAKE) clean -C $(tooldir);)

clean-assets:
	find . \( -iname '*.1bpp' -o -iname '*.4bpp' -o -iname '*.8bpp' -o -iname '*.gbapal' -o -iname '*.lz' -o -iname '*.striped' \) -exec rm {} +

clean:
	rm -f $(ROM) $(ELF) $(MAP)
	rm -r $(OBJ_DIR)
	

include graphics.mk

%.bin: ;
%.s: ;
%.png: ;
%.pal: ;
%.aif: ;

# dummy rule for now
%.phscr: ; 
%.phscr.lz: %.phscr ; $(GBAGFX) $< $@ -search 1

%.1bpp: %.png  ; $(GBAGFX) $< $@
%.4bpp: %.png  ; $(GBAGFX) $< $@
%.8bpp: %.png  ; $(GBAGFX) $< $@
%.8bpp.striped: %.png ; $(GBAGFX) $< $@
%.4bpp.striped: %.png ; $(GBAGFX) $< $@
%.gbapal: %.pal ; $(GBAGFX) $< $@
%.gbapal: %.png ; $(GBAGFX) $< $@
%.lz: % ; $(GBAGFX) $< $@
%.rl: % ; $(GBAGFX) $< $@

$(C_BUILDDIR)/agb_sram.o: CFLAGS := -O -mthumb-interwork

$(ROM): $(ELF)
	$(OBJCOPY) -O binary --gap-fill 0xff --pad-to $(ROM_END) $< $@
	$(GBAFIX) --silent -p $@

$(OBJ_DIR)/sym_iwram.txt: sym_iwram.txt
	cp sym_iwram.txt $(OBJ_DIR)

$(OBJ_DIR)/sym_ewram.txt: sym_ewram.txt
	cp sym_ewram.txt $(OBJ_DIR)

ifeq ($(RFTA),1)
# (the RFTA build: the music's 16 tracks, two tracks for sound players 2 and 3,
# the sound time for the background stripes and the bigger mixer in IWRAM; the
# mixer may take 100 scanlines, not 80: Rise from the Ashes' songs keep 12
# channels busy, and notes starting all at once take the sequencer up to 20)
LD_RFTA := -e 's@/\*RFTA_TEXT\*/@src/en_rfta.o(.text); src/en_rfta_rooms.o(.text); src/en_rfta_episodes.o(.text);@' \
	-e 's@/\*RFTA_RODATA\*/@src/en_rfta.o(.rodata); src/en_rfta_rooms.o(.rodata); src/en_rfta_tables.o(.rodata); src/en_rfta_episodes.o(.rodata);@' \
	-e 's@/\*RFTA_SECTION\*/@. = 0x9000000; rfta_data : ALIGN(4) { src/en_rfta.o(rfta_data); data/rfta/graphics.o(rfta_data); data/rfta/backgrounds.o(rfta_data); data/rfta/descriptions.o(rfta_data); data/rfta/characters.o(rfta_data); data/rfta/effects.o(rfta_data); data/rfta/music.o(rfta_data); data/rfta/sfx.o(rfta_data); } =0@' \
	-e 's@^gMaxLines = 80;@gMaxLines = 100;@' \
	-e 's@/\*RFTA_IWRAM\*/@. = 0x59D0; gMPlayTrack_BGM16 = .; . = 0x5ED0; gMPlayTrack_SE2x2 = .; . = 0x5F70; gMPlayTrack_SE3x2 = .; . = 0x6010; gEnSoundLines = .; . = 0x6020; gSoundMainRAM_BufferRfta = .;@'
endif

$(OBJ_DIR)/ld_script.ld: ld_script.txt $(OBJ_DIR)/sym_iwram.txt $(OBJ_DIR)/sym_ewram.txt
	cd $(OBJ_DIR) && sed -e "s#tools/#../../tools/#g" $(LD_RFTA) ../../ld_script.txt > ld_script.ld

$(ELF): %.elf: $(OBJS) $(OBJ_DIR)/ld_script.ld
	cd $(OBJ_DIR) && ../../$(LD) -T ld_script.ld -Map ../../$*.map -o ../../$@ $(OBJS_REL) -L ../../tools/agbcc/lib -lgcc -lc
	$(GBAFIX) -t"$(TITLE)" -c$(GAMECODE) -m$(MAKER_CODE) -r$(GAME_REVISION) --silent $@

$(ASM_BUILDDIR)/%.o: $(ASM_SUBDIR)/%.s
	$(AS) $(ASFLAGS) -o $@ $<

ifeq ($(NODEP),1)
$(DATA_ASM_BUILDDIR)/%.o: data_dep :=
else
$(DATA_ASM_BUILDDIR)/%.o: data_dep = $(shell $(SCANINC) -I include -I "" $(DATA_ASM_SUBDIR)/$*.s)
endif

$(DATA_ASM_BUILDDIR)/%.o: $(DATA_ASM_SUBDIR)/%.s $$(data_dep)
	$(AS) $(ASFLAGS) -o $@ $< 
	
ifeq ($(NODEP),1)
$(RODATA_ASM_BUILDDIR)/%.o: rodata_dep :=
else
$(RODATA_ASM_BUILDDIR)/%.o: rodata_dep = $(shell $(SCANINC) -I include -I "" $(RODATA_ASM_SUBDIR)/$*.s)
endif

$(RODATA_ASM_BUILDDIR)/%.o: $(RODATA_ASM_SUBDIR)/%.s $$(rodata_dep)
	$(AS) $(ASFLAGS) -o $@ $< 

ifeq ($(NODEP),1)
$(C_BUILDDIR)/%.o: c_dep :=
else
$(C_BUILDDIR)/%.o: c_dep = $(shell $(SCANINC) -I include $(C_SUBDIR)/$*.c)
endif
	
$(C_BUILDDIR)/%.o : $(C_SUBDIR)/%.c $$(c_dep)
	$(CPP) $(CPPFLAGS) $< -o $(C_BUILDDIR)/$*.i
	@$(PREPROC) $(C_BUILDDIR)/$*.i | $(CC1) $(CFLAGS) -o $(C_BUILDDIR)/$*.s
	@echo | sed "i.text\n\t.align\t2, 0" >> $(C_BUILDDIR)/$*.s
	$(AS) $(ASFLAGS) -o $@ $(C_BUILDDIR)/$*.s

ifeq ($(NODEP),1)
$(C_BUILDDIR)/%.o: c_asm_dep :=
else
$(C_BUILDDIR)/%.o: c_asm_dep = $(shell $(SCANINC) -I include -I "" $(C_SUBDIR)/$*.s)
endif

$(C_BUILDDIR)/%.o: $(C_SUBDIR)/%.s $$(c_asm_dep)
	$(AS) $(ASFLAGS) -o $@ $<

# English patch: before the scripts go into the ROM, check them against the
# Japanese ones (tools/en/check_scripts.py): no line on a screen faded to
# black where the Japanese game shows none, the same penalties and branches,
# jumps that land and lines that fit the text box.
# Skipped, with a warning, where python3 is not installed.
SCRIPT_CHECK := $(OBJ_DIR)/script_check.ok

$(SCRIPT_CHECK): tools/en/check_scripts.py tools/en/phscr.py tools/en/pdump.py graphics/vwf/font_widths.bin graphics/vwf/font_advance.bin $(wildcard script/*.phscr) $(wildcard script_en/*.phscr)
	@if command -v python3 >/dev/null 2>&1; then python3 tools/en/check_scripts.py; \
	else echo "warning: python3 not found, English script check skipped"; fi
	@touch $@

$(C_BUILDDIR)/scripts.o: $(SCRIPT_CHECK)

check-scripts:
	python3 tools/en/check_scripts.py

rev1:        ; @$(MAKE) GAME_REVISION=1
compare_rev1: ; @$(MAKE) GAME_REVISION=1 COMPARE=1
clean_rev1:   ; @$(MAKE) GAME_REVISION=1 clean