import librosa
import numpy as np
from pydub import AudioSegment
import os

def slice_audio_by_beats(audio_path: str, segment_duration_s: float, output_dir: str) -> list[str]:
    """
    Slices an audio file by drum beats into segments of a desired duration.

    Args:
        audio_path: Path to the input audio file.
        segment_duration_s: The desired duration of the output segments in seconds.
        output_dir: The directory to save the output segments.

    Returns:
        A list of paths to the created audio segments.
    """
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    print(f"Loading audio from {audio_path}...")
    y, sr = librosa.load(audio_path)
    
    print("Detecting beats...")
    tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
    beat_times = librosa.frames_to_time(beat_frames, sr=sr)
    
    full_duration = librosa.get_duration(y=y, sr=sr)
    # Ensure beat times are unique and sorted, including the start and end of the audio
    beat_times = np.unique(np.concatenate(([0.0], beat_times, [full_duration])))

    print(f"Found {len(beat_times)} beats.")

    segments = []
    current_segment_start_time = beat_times[0]
    
    for i in range(1, len(beat_times)):
        current_beat_time = beat_times[i]
        
        # Look ahead to decide the best cut.
        # If adding the next beat interval makes the segment closer to the target duration, we wait.
        if i + 1 < len(beat_times):
            next_beat_time = beat_times[i+1]
            err_current = abs((current_beat_time - current_segment_start_time) - segment_duration_s)
            err_next = abs((next_beat_time - current_segment_start_time) - segment_duration_s)
            
            # If the current segment is already over the target, or if cutting now is better than waiting
            if (current_beat_time - current_segment_start_time) > segment_duration_s and err_current <= err_next:
                segment_end_time = current_beat_time
            elif err_current <= err_next:
                 segment_end_time = current_beat_time
            else:
                continue # Skip to next beat, extending the current segment
        else:
             # This is the last possible cut point
             segment_end_time = current_beat_time

        segments.append((current_segment_start_time, segment_end_time))
        current_segment_start_time = segment_end_time

    # Ensure the last part of the audio is included
    if current_segment_start_time < full_duration:
        segments.append((current_segment_start_time, full_duration))

    print(f"Created {len(segments)} segments.")
    
    # Export segments
    print("Exporting segments...")
    audio = AudioSegment.from_file(audio_path)
    output_files = []
    base_filename = os.path.splitext(os.path.basename(audio_path))[0]

    for i, (start_s, end_s) in enumerate(segments):
        start_ms = int(start_s * 1000)
        end_ms = int(end_s * 1000)
        
        if start_ms >= end_ms:
            continue

        segment_audio = audio[start_ms:end_ms]
        
        output_filename = f"{base_filename}_segment_{i+1}.wav"
        output_path = os.path.join(output_dir, output_filename)
        
        segment_audio.export(output_path, format="wav")
        output_files.append(output_path)

    print(f"Finished exporting {len(output_files)} files to {output_dir}.")
    return output_files 