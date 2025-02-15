import argparse
from pathlib import Path
from functools import partial
import librosa
import soundfile as sf
import subprocess
import logging
import json
from auto_tune import autotune, closest_pitch, aclosest_pitch_from_scale
from sound_effects import apply_reverb, apply_delay, apply_compression
from source_separation import separate_sources
from video_audio_utils import (
    extract_audio_from_video, 
    add_audio_to_video, 
    mix_audio_with_ducking,
    standardize_video_dimensions
)

def setup_logging():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def main(video_file, plot=False, correction_method='scale', scale='C:maj', spread_factor=1.2, 
         background_music_path=None, vocals_volume=1.0, music_volume=0.8, other_volume=0.9,
         ducking_ratio=2.5, ducking_threshold=0.015, compression_params=None, 
         reverb_params=None, delay_params=None):
    setup_logging()
    
    video_filepath = Path(video_file)
    cache_dir = video_filepath.parent / (video_filepath.stem + '_output')
    cache_dir.mkdir(exist_ok=True)
    
    # Standardize video dimensions to 720x1280 if needed
    standardized_video = cache_dir / (video_filepath.stem + '_standardized' + video_filepath.suffix)
    if not standardized_video.exists():
        logging.info("Standardizing video dimensions to 720x1280")
        standardize_video_dimensions(video_filepath, standardized_video, target_width=720, target_height=1280)
        video_filepath = standardized_video
        logging.info(f"Video dimensions standardized: {standardized_video}")
    else:
        video_filepath = standardized_video
        logging.info(f"Standardized video already exists: {standardized_video}")

    audio_filepath = cache_dir / (video_filepath.stem + '_audio.wav')

    if not audio_filepath.exists():
        logging.info(f"Extracting audio from video {video_filepath}")
        extract_audio_from_video(video_filepath, audio_filepath)
        logging.info(f"Audio extracted to {audio_filepath}")
    else:
        logging.info(f"Audio file already exists: {audio_filepath}")

    logging.info(f"Starting source separation for {audio_filepath}")
    vocals_path, other_path = separate_sources(str(audio_filepath), str(cache_dir))
    logging.info(f"Source separation completed. Vocals: {vocals_path}, Other: {other_path}")

    # Apply compression to vocals first
    compressed_filepath = cache_dir / (Path(vocals_path).stem + '_compressed' + Path(vocals_path).suffix)
    if not compressed_filepath.exists():
        logging.info("Applying compression to vocals")
        if compression_params:
            apply_compression(str(vocals_path), str(compressed_filepath), **compression_params)
        else:
            apply_compression(str(vocals_path), str(compressed_filepath))
        logging.info(f"Compression completed. Output file: {compressed_filepath}")
    
    # Process vocals with autotune after compression
    y, sr = librosa.load(compressed_filepath, sr=None, mono=True)
    if y.ndim > 1:
        y = y[0, :]

    correction_function = closest_pitch if correction_method == 'closest' else \
        partial(aclosest_pitch_from_scale, scale=scale)

    corrected_filepath = cache_dir / (Path(compressed_filepath).stem + '_pitch_corrected' + Path(compressed_filepath).suffix)
    if not corrected_filepath.exists():
        logging.info("Starting autotune")

        #pitch_corrected_y = autotune(y, sr, correction_function, 2, min_note_duration=0, plot = plot)
        pitch_corrected_y = autotune(y, sr, correction_function, plot = plot)

        sf.write(str(corrected_filepath), pitch_corrected_y, sr)
        logging.info(f"Autotune completed. Pitch corrected file: {corrected_filepath}")
    else:
        logging.info(f"Pitch corrected file already exists: {corrected_filepath}")

    reverb_output_filepath = cache_dir / (Path(compressed_filepath).stem + '_pitch_corrected_reverb' + Path(compressed_filepath).suffix)
    if not reverb_output_filepath.exists():
        logging.info("Starting reverb application")
        if reverb_params:
            apply_reverb(str(corrected_filepath), str(reverb_output_filepath), **reverb_params)
        else:
            apply_reverb(str(corrected_filepath), str(reverb_output_filepath))
        logging.info(f"Reverb application completed. Reverb file: {reverb_output_filepath}")
    
    # Apply delay after reverb
    delay_output_filepath = cache_dir / (Path(compressed_filepath).stem + '_pitch_corrected_reverb_delay' + Path(compressed_filepath).suffix)
    if not delay_output_filepath.exists():
        logging.info("Starting delay application")
        if delay_params:
            apply_delay(str(reverb_output_filepath), str(delay_output_filepath), **delay_params)
        else:
            apply_delay(str(reverb_output_filepath), str(delay_output_filepath))
        final_vocals_path = delay_output_filepath
        logging.info(f"Delay application completed. Final vocals file: {delay_output_filepath}")
    else:
        final_vocals_path = delay_output_filepath
        logging.info(f"Delay file already exists: {delay_output_filepath}")

    # Remix all sources using ffmpeg with ducking
    final_audio_path = cache_dir / (audio_filepath.stem + '_final_mix' + audio_filepath.suffix)
    if not final_audio_path.exists():
        logging.info("Starting remixing with ducking effect")
        try:
            if background_music_path:
                mix_audio_with_ducking(
                    str(final_vocals_path),
                    str(other_path),
                    str(background_music_path),
                    str(final_audio_path),
                    vocals_volume=vocals_volume,
                    other_volume=other_volume,
                    music_volume=music_volume,
                    ducking_ratio=ducking_ratio,
                    ducking_threshold=ducking_threshold
                )
            else:
                # Original mixing without background music
                subprocess.run([
                    'ffmpeg',
                    '-i', str(final_vocals_path),
                    '-i', str(other_path),
                    '-filter_complex',
                    f'[0:a]volume={vocals_volume}[v1];[1:a]volume={other_volume}[v2];[v1][v2]amix=inputs=2:duration=longest',
                    '-y',
                    str(final_audio_path)
                ], check=True)
            logging.info(f"Remixing completed. Final audio file: {final_audio_path}")
        except subprocess.CalledProcessError as e:
            logging.error(f"Error during remixing: {str(e)}")
            raise
    else:
        logging.info(f"Final audio file already exists: {final_audio_path}")

    output_dir = Path('output')

    # Add the final audio back to the video with fade effects and logo
    final_video_path = output_dir / (video_filepath.stem + '_final' + video_filepath.suffix)
    if not final_video_path.exists():
        logging.info("Adding final audio back to video with effects")
        logo_path = Path('logo.jpg')
        logo_arg = str(logo_path) if logo_path.exists() else None
        add_audio_to_video(video_filepath, final_audio_path, final_video_path, 
                          fade_duration=3, logo_path=logo_arg)
        logging.info(f"Final video created: {final_video_path}")
    else:
        logging.info(f"Final video file already exists: {final_video_path}")

# Load configuration from config.json
with open('config.json', 'r') as config_file:
    config = json.load(config_file)

# Call the main function with values from the config file
main(
    video_file=config['video_file'],
    plot=config.get('plot', False),
    correction_method=config.get('correction_method', 'closest'),
    scale=config.get('scale'),
    spread_factor=config.get('spread_factor', 1.2),
    background_music_path=config.get('background_music_path'),
    vocals_volume=config.get('vocals_volume', 1.0),
    music_volume=config.get('music_volume', 0.8),
    other_volume=config.get('other_volume', 0.9),
    ducking_ratio=config.get('ducking_ratio', 2.5),
    ducking_threshold=config.get('ducking_threshold', 0.015),
    compression_params=config.get('compression'),
    reverb_params=config.get('reverb'),
    delay_params=config.get('delay')
)