Sticker DB (MongoDB) :) 


Structura unui obiect stocat in baza de date NoSQL (format JSON)

<img width="298" height="171" alt="HappyCatGIF" src="https://github.com/user-attachments/assets/b1939e66-7c28-4d33-bcae-21639e276025" />

{
  "key":         "STK-001",           
  "name":        "Happy Cat",         
  "description": "A very happy cat",  
  "image_url":   "https://...",        
  "price":       0.99,                
  "tags":        ["cat", "happy"],    
  "pack":        "Animals Vol.1",     
  "rarity":      "common",            
  "animated":    false,               
  "created_at":  "2024-01-01T...",    
  "updated_at":  "2024-01-01T..."     
}

  KEY = cheie unica (string)
  NAME = numele stickerului 
  DESCRIPTION = descriere
  IMAGE_URL = URL imagine/GIF
  PRICE = pret (float)
  TAGS = lista tags
  PACK = pachetul din care face parte
  RARITY ** = common | uncommon | rare | epic | legendary 
  ANIMATED = este GIF? (animat)
  CREATED_AT = timestamp creare (format ISO)
  UPDATED_AT = timestamp ultima modificare (format ISO)

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
