import os

def rename_mp3_files(folder_path):
    # Get list of all files in the folder
    files = os.listdir(folder_path)
    # Filter out only .mp3 files
    mp3_files = [file for file in files if file.endswith('.mp3')]
    
    # Start the numbering from 1
    count = 1
    for file in mp3_files:
        # Form the new filename
        new_name = f"{count}.mp3"
        # Rename the file
        os.rename(os.path.join(folder_path, file), os.path.join(folder_path, new_name))
        # Increment count for next file
        count += 1

# Replace 'folder_path' with the path to your folder containing .mp3 files
folder_path = r'C:\Users\dellpc\Desktop\123'
rename_mp3_files(folder_path)
