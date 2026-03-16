from scamp import *

# ================== Сессия ==================
s = Session(tempo=120)  # торжественный темп

# ================== Инструменты ==================
guitar = s.new_part("distortion_guitar")  # основная мелодия
bass = s.new_part("acoustic_bass")        # глубокий бас
drums = s.new_part("drums")               # ударные

# ================== Ноты ==================
notes = {
    "F2": 87.31,
    "G2": 98.00,
    "A2": 110.00,
    "C3": 130.81,
    "D3": 146.83,
    "F3": 174.61,
    "G3": 196.00,
    "A3": 220.00
}

# Торжественная мелодия
melody_notes = ["F2", "A2", "C3", "D3", "F3", "G3", "A3"]

# ================== Ударные паттерны ==================
drum_pattern = ["kick", "kick", "snare", "kick", "snare"]

# ================== Генерация мелодии ==================
for i in range(4):  # повторяем тему 4 раза
    for note_name in melody_notes:
        freq = notes[note_name]

        # Гитара
        guitar.play_note(freq, 1.5, 0.5)

        # Бас
        if melody_notes.index(note_name) % 2 == 0:
            bass_note = freq / 2
            bass.play_note(bass_note, 1.5, 0.4)

        # Ударные
        drum_type = drum_pattern[i % len(drum_pattern)]
        if drum_type == "kick":
            drums.play_note(36, 0.2, 0.6)  # MIDI нота 36 = бас-барабан
        else:
            drums.play_note(38, 0.2, 0.5)  # MIDI нота 38 = малый барабан

        s.wait(1.5)
# ================== Сохраняем как MIDI ==================
s.save_midi("cicada_grand_theme.mid")
print("Готово! Файл 'cicada_grand_theme.mid' создан.")