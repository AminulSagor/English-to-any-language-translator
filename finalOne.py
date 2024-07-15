from moviepy.editor import *
from google.cloud import speech_v1p1beta1 as speech
from googletrans import Translator
import os
from pydub import AudioSegment, effects
from gtts import gTTS


# Provide the path to your JSON key file
key_path = "/content/our-bruin-405017-430889f96470 (2).json"
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = key_path

def extract_background_music(video_path):
    # Separate Audio using Spleeter
    os.system(f"spleeter separate -o . -c mp3 {video_path}")

    # Load the accompaniment track extracted by Spleeter
    audio_path = f"{video_path[0:-4]}/accompaniment.mp3"
    return AudioFileClip(audio_path)

def extend_audio_to_match_video(audio_path, video_duration):
    audio = AudioSegment.from_file(audio_path)

    # Calculate the duration of the audio and video
    audio_duration = len(audio) / 1000  # Convert milliseconds to seconds

    # Calculate the duration difference between audio and video
    duration_diff = video_duration - audio_duration

    # If the audio is shorter than the video, extend it by adding silence
    if duration_diff > 0:
        silence = AudioSegment.silent(duration=int(duration_diff * 1000))  # Duration in milliseconds
        extended_audio = audio + silence

        # Return the extended audio directly
        return extended_audio
    else:
        # If the audio matches or exceeds the video duration, return the original audio
        return audio

def transcribe_and_translate(video_path, target_language):
    video = VideoFileClip(video_path)

    # Extract audio from the video
    audio = video.audio

    temp_dir = "/content/temp_audio"
    os.makedirs(temp_dir, exist_ok=True)

    # Export audio from the video
    audio_file_path = os.path.join(temp_dir, "original_audio.wav")
    audio.write_audiofile(audio_file_path, codec='pcm_s16le')

    # Convert audio to mono
    sound = AudioSegment.from_wav(audio_file_path)
    sound = sound.set_channels(1)
    sound.export(audio_file_path, format="wav")

    # Apply noise reduction
    cutoff_frequency = 1500  # You can adjust this value
    sound = sound.low_pass_filter(cutoff_frequency)

    # Create a Speech-to-Text client
    client = speech.SpeechClient()

    # Read the audio file
    with open(audio_file_path, 'rb') as audio_file:
        content = audio_file.read()

    # Configure the audio settings
    config = speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
        sample_rate_hertz=44100,  # Update the sample rate to match your audio
        language_code="en-US",
        enable_word_time_offsets=True  # Request word-level timing information
    )

    # Perform the speech recognition
    audio = speech.RecognitionAudio(content=content)
    response = client.recognize(config=config, audio=audio)

    # Translate and store the transcribed text with time tokens
    text_and_times = []

    # Initialize translator
    translator = Translator()

    # Translate and store the transcribed text with time tokens
    for result in response.results:
        start_time = result.alternatives[0].words[0].start_time.total_seconds()
        end_time = result.alternatives[0].words[-1].end_time.total_seconds()

        # Translate each sentence to the target language
        sentence = ' '.join([word_info.word for word_info in result.alternatives[0].words])
        translated_sentence = translator.translate(sentence, dest=target_language)
        translated_text = translated_sentence.text if translated_sentence else ""

        # Store the translated text and time tokens
        text_and_times.append((translated_text, start_time, end_time))

    # Initialize the concatenated audio
    concatenated_audio = AudioSegment.silent(duration=0)

    # Generate audio from translated text with time tokens
    for text, start_time, end_time in text_and_times:
        tts = gTTS(text=text, lang=target_language)

        # Save the gTTS output as an MP3 file
        mp3_filename = os.path.join(temp_dir, "temp_audio.mp3")
        tts.save(mp3_filename)

        # Convert the MP3 file to WAV using pydub
        audio_segment = AudioSegment.from_mp3(mp3_filename)

        # Calculate the exact duration of the translated audio segment
        translated_duration = end_time - start_time

        # Calculate the time difference between the current sentence and the last sentence
        time_difference = start_time * 1000 - len(concatenated_audio)

        # If there is a time difference, add silence to align with the start time
        if time_difference > 0:
            concatenated_audio += AudioSegment.silent(duration=int(time_difference))

        # Concatenate the adjusted audio segment
        concatenated_audio += audio_segment[:int(translated_duration * 1000)]

        # Remove the temporary MP3 file
        os.remove(mp3_filename)

    # Save the concatenated audio as a WAV file
    translated_audio_path = os.path.join(temp_dir, "translated_audio.wav")
    concatenated_audio.export(translated_audio_path, format="wav")

    return translated_audio_path

def synchronize_audio_with_video(video_path, audio_path):
    video = VideoFileClip(video_path)
    audio = AudioSegment.from_file(audio_path)

    # Ensure matching durations
    if len(audio) / 1000 < video.duration:
        # Extend the audio to match the video duration
        audio = extend_audio_to_match_video(audio_path, video.duration)

    # Trim or overlay audio to match video duration exactly
    audio = audio[:int(video.duration * 1000)]  # Convert seconds to milliseconds

    # Export synchronized audio to a temporary file
    synchronized_audio_path = os.path.join("/content/temp_audio", "synchronized_audio.wav")
    audio.export(synchronized_audio_path, format="wav")

    # Set video audio to the synchronized audio file
    video = video.set_audio(AudioFileClip(synchronized_audio_path))

    # Output synchronized video with audio
    output_path = "synchronized_video.mp4"
    video.write_videofile(output_path, codec="libx264", audio_codec="aac")

    return output_path

def extract_background_music(video_path):
    # Separate Audio using Spleeter
    os.system(f"spleeter separate -o . -c mp3 {video_path}")

    # Load the accompaniment track extracted by Spleeter
    audio_path = f"{video_path[0:-4]}/accompaniment.mp3"
    return AudioFileClip(audio_path)


if __name__ == "__main__":

    video_path = input("Enter the path to the video file: ")
    target_language = input("Enter the target language code for translation: ")

    translated_audio = transcribe_and_translate(video_path, target_language)

    synchronized_video = synchronize_audio_with_video(video_path, translated_audio)

    # Extract the background music using Spleeter
    background_music = extract_background_music(video_path)

    # Load the synchronized video
    synchronized_clip = VideoFileClip(synchronized_video)

    # Ensure the duration of the background music matches the synchronized video duration
    if background_music.duration < synchronized_clip.duration:
        background_music = background_music.fx(afx.audio_loop, duration=synchronized_clip.duration)

    # Load audio from synchronized video
    synchronized_audio = synchronized_clip.audio

    # Set the combined audio to the synchronized video
    final_audio = CompositeAudioClip([synchronized_audio, background_music])
    final_clip_with_music = synchronized_clip.set_audio(final_audio)

    # Export the final video with the combined audio using MoviePy
    output_video_path = "final_video_with_background_music.mp4"
    final_clip_with_music.write_videofile(output_video_path, codec='libx264', audio_codec='aac', fps=24)

    print(f"Final video with background music saved at: {output_video_path}")

    # Delete unnecessary files
    os.remove(translated_audio)
    os.remove(synchronized_video)
