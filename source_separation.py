import os
from pathlib import Path
import torch
import torchaudio
import logging
from demucs.pretrained import get_model
from demucs.apply import apply_model

def separate_sources(input_file, output_dir):
    # Ensure the output directory exists
    os.makedirs(output_dir, exist_ok=True)
    
    # Define paths for the separated sources - only vocals and others
    source_names = ["vocals", "other"]
    output_paths = {
        name: str(Path(output_dir) / f"{name}_output.wav")
        for name in source_names
    }
    
    # Check if the separated sources already exist
    if all(Path(path).exists() for path in output_paths.values()):
        return tuple(output_paths.values())
    
    # Load the model (will download if not present)
    model = get_model('htdemucs_ft')  # Using mdx model which is optimized for vocals separation
    model.cuda() if torch.cuda.is_available() else model.cpu()
    
    # Load and process audio with error handling
    try:
        wav, sr = torchaudio.load(input_file)
    except Exception as e:
        logging.error(f"Failed to load audio file: {str(e)}")
        raise
    
    # Ensure stereo audio (duplicate mono if necessary)
    if wav.shape[0] == 1:
        wav = torch.cat([wav, wav], dim=0)
    elif wav.shape[0] > 2:
        wav = wav[:2]  # Take only first two channels if more than stereo
    
    # Handle potential NaN or Inf values
    if torch.isnan(wav).any() or torch.isinf(wav).any():
        wav = torch.nan_to_num(wav, nan=0.0, posinf=1.0, neginf=-1.0)
    
    # Ensure we're working with the right shape and format
    wav = wav.float()  # Ensure float32
    
    # Normalize properly with safety checks
    wav = wav / max(1.0, wav.abs().max())
    
    # Match sample rate if needed (Demucs expects 44100)
    if sr != 44100:
        resampler = torchaudio.transforms.Resample(sr, 44100)
        wav = resampler(wav)
        sr = 44100
    
    # Add small padding to prevent edge effects
    pad_length = 44100 * 2  # 2 seconds of padding
    wav = torch.nn.functional.pad(wav, (pad_length, pad_length), mode='reflect')
    
    # Separate
    try:
        with torch.no_grad():
            sources = apply_model(model, wav.unsqueeze(0), progress=True, shifts=2, split=True, overlap=0.25)[0]
            # Demucs returns sources in the order: drums, bass, other, vocals
            # We only want vocals and a mix of everything else
            sources = sources.cpu()
            
            # Extract vocals (last stem)
            vocals = sources[-1]  # Get vocals (last source)
            
            # Mix all other sources together for "other"
            other = torch.sum(sources[:-1], dim=0)  # Sum all except vocals
            
            # Remove padding
            vocals = vocals[..., pad_length:-pad_length]
            other = other[..., pad_length:-pad_length]
            
            # Save sources
            torchaudio.save(output_paths["vocals"], vocals, sr)
            torchaudio.save(output_paths["other"], other, sr)
            
            return tuple(output_paths.values())
    except Exception as e:
        logging.error(f"Error during source separation: {str(e)}")
        raise