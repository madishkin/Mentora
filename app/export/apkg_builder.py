import tempfile
from pathlib import Path
import genanki

def build_apkg(cards: list[dict], deck_name: str) -> bytes:
    """
    Builds an Anki package (.apkg) from a list of card dicts.
    Each card dict should have: 'front', 'back', and optional 'tags'.
    """
    # Generate consistent IDs based on the deck name so updates work correctly in Anki
    model_id = abs(hash(deck_name + "model")) % (10 ** 10)
    deck_id = abs(hash(deck_name + "deck")) % (10 ** 10)
    
    my_model = genanki.Model(
      model_id,
      'Mentora Basic Model',
      fields=[
        {'name': 'Question'},
        {'name': 'Answer'},
      ],
      templates=[
        {
          'name': 'Card 1',
          'qfmt': '{{Question}}',
          'afmt': '{{FrontSide}}<hr id="answer">{{Answer}}',
        },
      ])
      
    my_deck = genanki.Deck(deck_id, deck_name)
    
    for card in cards:
        tags = card.get('tags', [])
        # genanki tags shouldn't contain spaces
        clean_tags = [t.replace(' ', '_') for t in tags]
        
        note = genanki.Note(
          model=my_model,
          fields=[card.get('front', ''), card.get('back', '')],
          tags=clean_tags
        )
        my_deck.add_note(note)
        
    my_package = genanki.Package(my_deck)
    
    with tempfile.NamedTemporaryFile(delete=False, suffix=".apkg") as tf:
        temp_path = tf.name
        
    try:
        my_package.write_to_file(temp_path)
        with open(temp_path, "rb") as f:
            data = f.read()
        return data
    finally:
        Path(temp_path).unlink(missing_ok=True)
