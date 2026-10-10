# Gyakuten Saiban 1 English

<img width="450" height="282" alt="image" src="https://github.com/user-attachments/assets/b0044f05-d641-4705-8bd4-0b9d4a69b693" />

An English translation that backports the script from the official 2005 DS game. 
<img width="1488" height="676" alt="image" src="https://github.com/user-attachments/assets/d201b9c6-6e78-4001-a97c-2789ec49c61d" />


<img width="1568" height="527" alt="image" src="https://github.com/user-attachments/assets/c4b5cdb1-9d80-460f-af7b-75fce57196b7" />



## Building

This repository is the full source of the hack, built on the decompilation of
Gyakuten Saiban (GBA). Set up agbcc and binutils as described in
[BUILDING.md](BUILDING.md) (the decompilation's own instructions), then:

```
make tools
make
```

The result is the patched English ROM. The scripts that make the English
version (script port, graphics, effects, courtroom) are in `tools/en`.

## Credits

- The pwaa1 decompilation of Gyakuten Saiban
  ([atasro2/pwaa1](https://github.com/atasro2/pwaa1)) and everyone who worked
  on it. This project would not exist without it.
- English script and text graphics: the official English release of
  Phoenix Wright: Ace Attorney (Nintendo DS, 2005), by Capcom.
- Courtroom backgrounds: Gyakuten Saiban 3 (GBA, 2004), by Capcom.
