import subprocess
from pathlib import Path

def extract_audio_from_video(video_file, output_audio_file):
    subprocess.run([
        'ffmpeg', '-i', str(video_file), '-q:a', '0', '-map', 'a', str(output_audio_file)
    ])

import subprocess
from pathlib import Path

def scale_logo(logo_path, scaled_logo_path, max_logo_width=200):
    """
    Scales the logo to a maximum width while maintaining aspect ratio.
    """
    subprocess.run([
        'ffmpeg', '-i', str(logo_path),
        '-vf', f'scale=w={max_logo_width}:h=-1',
        str(scaled_logo_path)
    ])


def add_audio_to_video(video_file, audio_file, output_video_file, fade_duration=3, logo_path=None):
    # Get video duration for accurate fade timing
    video_duration = float(subprocess.check_output([
        'ffprobe', '-v', 'error', '-show_entries', 'format=duration',
        '-of', 'default=noprint_wrappers=1:nokey=1', str(video_file)
    ]).decode().strip())
    
    # Check if logo scaling is needed
    scaled_logo_path = "scaled_logo.jpg"
    if logo_path and Path(logo_path).exists():
        scale_logo(logo_path, scaled_logo_path)
        filter_complex = (
            f'[0:v]fade=t=in:st=0:d={fade_duration},'
            f'fade=t=out:st={video_duration-fade_duration}:d={fade_duration}[vfade];'
            f'[2:v]format=rgba[logo];'  # Ensure logo has correct format
            '[vfade][logo]overlay=x=main_w-overlay_w-20:y=main_h-overlay_h-20[v];'  # Position logo at bottom-right
            f'[1:a]afade=t=in:st=0:d={fade_duration},'
            f'afade=t=out:st={video_duration-fade_duration}:d={fade_duration}[audio]'
        )
        input_args = ['-i', str(video_file), '-i', str(audio_file), '-i', scaled_logo_path]
    else:
        filter_complex = (
            f'[0:v]fade=t=in:st=0:d={fade_duration},'
            f'fade=t=out:st={video_duration-fade_duration}:d={fade_duration}[v];'
            f'[1:a]afade=t=in:st=0:d={fade_duration},'
            f'afade=t=out:st={video_duration-fade_duration}:d={fade_duration}[audio]'
        )
        input_args = ['-i', str(video_file), '-i', str(audio_file)]

    # Run the ffmpeg command
    subprocess.run([
        'ffmpeg',
        *input_args,
        '-filter_complex', filter_complex,
        '-map', '[v]',
        '-map', '[audio]',
        '-c:v', 'libx264',
        '-preset', 'medium',
        '-crf', '23',
        '-c:a', 'aac',
        '-b:a', '192k',
        str(output_video_file)
    ])

def mix_audio_with_ducking(vocals_path, other_path, bg_music_path, output_path, duck_amount=0.6,
                     vocals_volume=1.0, other_volume=0.9, music_volume=0.8, 
                     ducking_ratio=2.5, ducking_threshold=0.015):
    """
    Mix audio files with enhanced ducking effect on background music when vocals are present
    
    Parameters:
        vocals_path: Path to vocals audio file
        other_path: Path to other instruments audio file
        bg_music_path: Path to background music file
        output_path: Path for output mixed file
        duck_amount: Amount of ducking (0.0 to 1.0, higher means more ducking)
        vocals_volume: Volume level for vocals (default: 1.0)
        other_volume: Volume level for other instruments (default: 0.9)
        music_volume: Volume level for background music (default: 0.8)
        ducking_ratio: Compression ratio for ducking effect (default: 2.5)
        ducking_threshold: Threshold for triggering ducking (default: 0.015)
    """
    # Calculate ducking parameters
    attack = 50       # Attack time in milliseconds
    release = 300     # Release time in milliseconds
    
    filter_complex = [
        # Split vocals for both mixing and sidechain detection
        '[0:a]asplit=2[vorig][vside]',
        
        # Prepare vocals detection signal with enhanced parameters
        '[vside]agate=threshold=0.1:ratio=2:attack=10:release=100[vgate]',
        
        # Process background music with volume adjustment
        f'[2:a]volume={music_volume}[bgm]',
        
        # Apply enhanced sidechain compression to background music
        f'[bgm][vgate]sidechaincompress=threshold={ducking_threshold}:ratio={ducking_ratio}'
        f':attack={attack}:release={release}:level_in=0.8:level_sc=1[ducked_bgm]',
        
        # Adjust levels for vocals and other instruments
        f'[vorig]volume={vocals_volume}[vocals]',
        f'[1:a]volume={other_volume}[other]',
        
        # Final mix with adjusted volumes and enhanced crossfading
        '[vocals][other][ducked_bgm]amix=inputs=3:duration=longest:weights=1 1 0.5'
    ]
    
    subprocess.run([
        'ffmpeg',
        '-i', str(vocals_path),
        '-i', str(other_path),
        '-i', str(bg_music_path),
        '-filter_complex',
        ';'.join(filter_complex),
        '-ac', '2',        # Ensure stereo output
        '-ar', '44100',    # Set sample rate
        '-y',
        str(output_path)
    ])

def get_video_dimensions(video_path):
    """Get the width and height of a video file"""
    cmd = [
        'ffprobe', '-v', 'error', '-select_streams', 'v:0',
        '-show_entries', 'stream=width,height',
        '-of', 'csv=s=x:p=0', str(video_path)
    ]
    dimensions = subprocess.check_output(cmd).decode().strip().split('x')
    return int(dimensions[0]), int(dimensions[1])

def standardize_video_dimensions(input_video, output_video, target_width=720, target_height=1280):
    """
    Crop/pad and scale video to target dimensions while maintaining aspect ratio
    """
    current_width, current_height = get_video_dimensions(input_video)
    
    # Calculate scaling and cropping parameters
    current_ratio = current_width / current_height
    target_ratio = target_width / target_height
    
    if current_ratio > target_ratio:
        # Video is too wide, need to crop width
        scale_height = target_height
        scale_width = int(current_width * (target_height / current_height))
        crop_x = (scale_width - target_width) // 2
        filter_complex = f'scale={scale_width}:{scale_height},crop={target_width}:{target_height}:{crop_x}:0'
    else:
        # Video is too tall, need to crop height
        scale_width = target_width
        scale_height = int(current_height * (target_width / current_width))
        crop_y = (scale_height - target_height) // 2
        filter_complex = f'scale={scale_width}:{scale_height},crop={target_width}:{target_height}:0:{crop_y}'
    
    subprocess.run([
        'ffmpeg', '-i', str(input_video),
        '-vf', filter_complex,
        '-c:a', 'copy',
        '-y', str(output_video)
    ])