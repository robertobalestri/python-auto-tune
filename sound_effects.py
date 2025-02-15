import numpy as np
import scipy.signal as signal
import librosa
import soundfile as sf

import numpy as np
import librosa
import soundfile as sf
from pedalboard import Pedalboard, Reverb, Delay, Compressor

def apply_reverb(input_file, output_file, room_size=0.3, damping=0.3, wet_level=0.3, dry_level=0.7):
    """
    Applies high-quality reverb to an audio file using Pedalboard.

    Parameters:
        input_file (str): Path to the input audio file.
        output_file (str): Path to save the output audio file.
        room_size (float): Size of the virtual room (0 to 1).
        damping (float): High-frequency damping (0 to 1).
        wet_level (float): Level of the wet (reverberated) signal (0 to 1).
        dry_level (float): Level of the dry (original) signal (0 to 1).
    """
    # Load audio
    audio, sr = librosa.load(input_file, sr=44100, mono=False)
    
    # If audio is mono, duplicate to stereo
    if len(audio.shape) == 1:
        audio = np.array([audio, audio])
    
    # Normalize audio
    audio = audio / np.max(np.abs(audio))
    
    # Create a Pedalboard with Reverb
    board = Pedalboard([
        Reverb(
            room_size=room_size,  # Controls the size of the virtual room
            damping=damping,     # Controls high-frequency damping
            wet_level=wet_level, # Level of the reverb effect
            dry_level=dry_level  # Level of the original signal
        )
    ])
    
    # Apply reverb
    processed_audio = board(audio, sr)
    
    # Normalize output
    processed_audio = processed_audio / np.max(np.abs(processed_audio))
    
    # Save the result
    sf.write(output_file, processed_audio.T, sr, subtype='PCM_16')


def apply_delay(input_file, output_file, delay_time=0.5, feedback=0.5, wet_level=0.2):
    """
    Applies a longer delay with a low wet level to an audio file using Pedalboard.

    Parameters:
        input_file (str): Path to the input audio file.
        output_file (str): Path to save the output audio file.
        delay_time (float): Delay time in seconds.
        feedback (float): Feedback amount for the delay (0 to 1).
        wet_level (float): Level of the wet (delayed) signal (0 to 1).
    """
    # Load audio
    audio, sr = librosa.load(input_file, sr=44100, mono=False)
    
    # If audio is mono, duplicate to stereo
    if len(audio.shape) == 1:
        audio = np.array([audio, audio])
    
    # Normalize audio
    audio = audio / np.max(np.abs(audio))
    
    # Create a Pedalboard with Delay
    board = Pedalboard([
        Delay(
            delay_seconds=delay_time,  # Delay time in seconds
            feedback=feedback,          # Feedback amount
            mix=wet_level               # Wet level of the delay
        )
    ])
    
    # Apply delay
    processed_audio = board(audio, sr)
    
    # Normalize output
    processed_audio = processed_audio / np.max(np.abs(processed_audio))
    
    # Save the result
    sf.write(output_file, processed_audio.T, sr, subtype='PCM_16')


def apply_compression(input_file, output_file, threshold_db=-20, ratio=4, attack_ms=10, release_ms=100):
    """
    Applies compression to an audio file using Pedalboard.

    Parameters:
        input_file (str): Path to the input audio file
        output_file (str): Path to save the output audio file
        threshold_db (float): Threshold in dB where compression starts
        ratio (float): Compression ratio
        attack_ms (float): Attack time in milliseconds
        release_ms (float): Release time in milliseconds
    """
    # Load audio
    audio, sr = librosa.load(input_file, sr=44100, mono=False)
    
    # If audio is mono, duplicate to stereo
    if len(audio.shape) == 1:
        audio = np.array([audio, audio])
    
    # Create a Pedalboard with Compressor
    board = Pedalboard([
        Compressor(
            threshold_db=threshold_db,
            ratio=ratio,
            attack_ms=attack_ms,
            release_ms=release_ms
        )
    ])
    
    # Apply compression
    processed_audio = board(audio, sr)
    
    # Normalize output
    processed_audio = processed_audio / np.max(np.abs(processed_audio))
    
    # Save the result
    sf.write(output_file, processed_audio.T, sr, subtype='PCM_16')