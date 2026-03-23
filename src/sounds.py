# =============================================================================
# Group: [Your Group Number]
# Date: 2026-03-16
# Members: [Names]
# =============================================================================

"""
Programmatic sound effects using pygame.mixer and numpy sine waves.
No external sound files needed. All sounds are generated in memory.
"""

import numpy as np
import pygame
from src.config import SOUND_ENABLED, SOUND_VOLUME


def _generate_tone(frequency, duration, sample_rate=22050, volume=0.5):
    """Generate a sine wave tone as a numpy array."""
    n_samples = int(sample_rate * duration)
    t = np.linspace(0, duration, n_samples, dtype=np.float32)
    wave = np.sin(2.0 * np.pi * frequency * t) * volume
    # Apply fade-in and fade-out envelope to avoid clicks
    fade_len = min(int(n_samples * 0.1), 200)
    if fade_len > 0:
        wave[:fade_len] *= np.linspace(0, 1, fade_len, dtype=np.float32)
        wave[-fade_len:] *= np.linspace(1, 0, fade_len, dtype=np.float32)
    return wave


def _wave_to_sound(wave, sample_rate=22050):
    """Convert a float32 mono wave array to a pygame Sound object."""
    # Convert to 16-bit signed integer
    wave_int = np.clip(wave * 32767, -32767, 32767).astype(np.int16)
    mixer_init = pygame.mixer.get_init()
    channels = mixer_init[2] if mixer_init else 2
    if channels <= 1:
        sound_array = wave_int
    else:
        sound_array = np.repeat(wave_int[:, None], channels, axis=1)
    sound = pygame.sndarray.make_sound(sound_array)
    return sound


class SoundManager:
    """Manages all programmatic sound effects."""

    def __init__(self):
        self.enabled = SOUND_ENABLED
        self.volume = SOUND_VOLUME
        self._sounds = {}
        self._initialized = False
        self._geiger_counter = 0
        self._init_sounds()

    def _init_sounds(self):
        """Generate all sound effects programmatically."""
        if not self.enabled:
            return
        try:
            # Ensure mixer is initialized with compatible settings
            if not pygame.mixer.get_init():
                pygame.mixer.init(frequency=22050, size=-16, channels=2)
            self._initialized = True
        except Exception:
            self.enabled = False
            return

        sr = 22050

        # Geiger click: very short noise burst
        click_duration = 0.05
        n = int(sr * click_duration)
        click_wave = (np.random.rand(n).astype(np.float32) - 0.5) * 0.3
        fade = min(n // 4, 50)
        if fade > 0:
            click_wave[:fade] *= np.linspace(0, 1, fade, dtype=np.float32)
            click_wave[-fade:] *= np.linspace(1, 0, fade, dtype=np.float32)
        self._sounds["geiger"] = _wave_to_sound(click_wave, sr)

        # Pickup: short rising tone (300 -> 600 Hz over 0.15s)
        dur = 0.15
        n = int(sr * dur)
        t = np.linspace(0, dur, n, dtype=np.float32)
        freq = np.linspace(300, 600, n, dtype=np.float32)
        pickup_wave = np.sin(2.0 * np.pi * freq * t) * 0.4
        fade = min(n // 5, 100)
        if fade > 0:
            pickup_wave[:fade] *= np.linspace(0, 1, fade, dtype=np.float32)
            pickup_wave[-fade:] *= np.linspace(1, 0, fade, dtype=np.float32)
        self._sounds["pickup"] = _wave_to_sound(pickup_wave, sr)

        # Transform: two-tone chord (400 + 500 Hz for 0.2s)
        dur = 0.2
        t = np.linspace(0, dur, int(sr * dur), dtype=np.float32)
        chord = (np.sin(2.0 * np.pi * 400 * t) +
                 np.sin(2.0 * np.pi * 500 * t)) * 0.25
        n = len(chord)
        fade = min(n // 5, 100)
        if fade > 0:
            chord[:fade] *= np.linspace(0, 1, fade, dtype=np.float32)
            chord[-fade:] *= np.linspace(1, 0, fade, dtype=np.float32)
        self._sounds["transform"] = _wave_to_sound(chord, sr)

        # Dispose: descending tone (600 -> 200 Hz over 0.25s)
        dur = 0.25
        n = int(sr * dur)
        t = np.linspace(0, dur, n, dtype=np.float32)
        freq = np.linspace(600, 200, n, dtype=np.float32)
        dispose_wave = np.sin(2.0 * np.pi * freq * t) * 0.4
        fade = min(n // 5, 100)
        if fade > 0:
            dispose_wave[:fade] *= np.linspace(0, 1, fade, dtype=np.float32)
            dispose_wave[-fade:] *= np.linspace(1, 0, fade, dtype=np.float32)
        self._sounds["dispose"] = _wave_to_sound(dispose_wave, sr)

        # Game over: ominous low tone (80 Hz for 0.3s with some modulation)
        dur = 0.3
        n = int(sr * dur)
        t = np.linspace(0, dur, n, dtype=np.float32)
        gameover_wave = (np.sin(2.0 * np.pi * 80 * t) * 0.5 +
                         np.sin(2.0 * np.pi * 120 * t) * 0.3)
        fade = min(n // 4, 200)
        if fade > 0:
            gameover_wave[:fade] *= np.linspace(0, 1, fade, dtype=np.float32)
            gameover_wave[-fade:] *= np.linspace(1, 0, fade, dtype=np.float32)
        self._sounds["gameover"] = _wave_to_sound(gameover_wave, sr)

        # Mutate: quick warble (350 Hz with vibrato for 0.15s)
        dur = 0.15
        n = int(sr * dur)
        t = np.linspace(0, dur, n, dtype=np.float32)
        vibrato = np.sin(2.0 * np.pi * 8 * t) * 50
        mutate_wave = np.sin(2.0 * np.pi * (350 + vibrato) * t) * 0.35
        fade = min(n // 5, 80)
        if fade > 0:
            mutate_wave[:fade] *= np.linspace(0, 1, fade, dtype=np.float32)
            mutate_wave[-fade:] *= np.linspace(1, 0, fade, dtype=np.float32)
        self._sounds["mutate"] = _wave_to_sound(mutate_wave, sr)

        # Set volume on all sounds
        for s in self._sounds.values():
            s.set_volume(self.volume)

    def play(self, name):
        """Play a named sound effect."""
        if not self.enabled or not self._initialized:
            return
        sound = self._sounds.get(name)
        if sound:
            sound.play()

    def play_geiger(self, waste_level, threshold):
        """Play geiger clicks based on waste level. Call each frame."""
        if not self.enabled or not self._initialized:
            return
        if waste_level <= 0:
            return
        # Higher waste = more frequent clicks
        ratio = min(1.0, waste_level / max(threshold, 1))
        # Click probability per frame: scales from ~0.01 to ~0.15
        click_prob = 0.01 + ratio * 0.14
        self._geiger_counter += click_prob
        if self._geiger_counter >= 1.0:
            self._geiger_counter -= 1.0
            self._sounds["geiger"].play()
