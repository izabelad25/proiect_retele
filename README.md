Sticker DB (MongoDB) :) 


Structura unui obiect stocat in baza de date NoSQL (format JSON)

<img width="298" height="171" alt="HappyCatGIF" src="https://github.com/user-attachments/assets/b1939e66-7c28-4d33-bcae-21639e276025" />

{
  "key":         "STK-001",           // cheie unica (string)
  "name":        "Happy Cat",         // numele stickerului
  "description": "A very happy cat",  // descriere
  "image_url":   "https://...",        // URL imagine/GIF
  "price":       0.99,                 // pret (float)
  "tags":        ["cat", "happy"],    // lista tags
  "pack":        "Animals Vol.1",     // pachetul din care face parte
  "rarity":      "common",            // common | uncommon | rare | epic | legendary 
  "animated":    false,               // este GIF? (animat)
  "created_at":  "2024-01-01T...",    // timestamp creare (format ISO)
  "updated_at":  "2024-01-01T..."     // timestamp ultima modificare (format ISO)
}
  

**instructiuni...

SERVER 
  > PORNIRE  (docker) --> docker-compose up --build
  > OPRIRE  (docker) --> docker-compose down

CLIENT

> GUI --> python client/client.py
> CLI --> python client/client_cli.py

COMENZI DISPONIBILE (command line interface)

    select                       = selecteaza TOATE stickerele
    select key <KEY>             = selecteaza in functie de KEY
    select prefix <PREFIX>       = selecteaza in functie de KEY PREFIX
    select name <TEXT>           = selecteaza in functie de NUME
    select tag <TAG>             = selecteaza in functie de TAG
    update <KEY> <FIELD> <VALUE> = ACTUALIZEAZA un camp al unui STICKER
    delete <KEY>                 = STERGE un sticker
    help                         = afiseaza instructiuni
    quit / exit                  = deconectare / exit
