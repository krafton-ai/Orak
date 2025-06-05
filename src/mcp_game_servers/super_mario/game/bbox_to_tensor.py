import os
import json
from PIL import Image
import torch
import numpy as np

ASSET_PATH = "src/gaming_slm/games/super_mario/assets"

def list_all_json_files(folder_path):
    json_file_list = []
    
    # Iterate over all files in the directory
    for filename in os.listdir(folder_path):
        if filename.endswith('.json'):
            json_file_list.append(filename)
    
    return json_file_list

def extract_bbox_as_tensor(json_data):

    # Decode image data
    image = Image.open(ASSET_PATH+'/screenshot/'+json_data['imagePath'])
    
    # Get bbox coordinates from points
    points = json_data['shapes'][0]['points']
    x1, y1 = points[0]
    x2, y2 = points[1]
    
    # Calculate top-left and bottom-right coordinates
    left = int(min(x1, x2))
    upper = int(min(y1, y2))
    right = int(max(x1, x2))
    lower = int(max(y1, y2))
    
    # Crop the region
    cropped_img = image.crop((left, upper, right, lower))
    
    # Convert image data to torch tensor
    tensor_img = torch.from_numpy(np.array(cropped_img)).float() / 255.0  # Normalize pixel values to [0, 1]
    
    # Change channel order (HWC -> CHW)
    tensor_img = tensor_img.permute(2, 0, 1)
    
    return tensor_img

def save_tensor_as_image(tensor_img, output_path):
    # Change channel order back to HWC
    img_array = tensor_img.permute(1, 2, 0).numpy() * 255.0
    img_array = img_array.astype(np.uint8)
    
    # Convert to PIL Image
    img = Image.fromarray(img_array)
    
    # Save image
    img.save(output_path)


# Get JSON files
json_data_list = list_all_json_files(ASSET_PATH)
print(json_data_list)


object_patterns = {}
for i, json_file in enumerate(json_data_list):

    # Load JSON data
    file_path = f'{ASSET_PATH}/{json_file}'
    with open(file_path, 'r') as f:
        json_data = json.load(f)

    # Call the function to get the image tensor
    tensor_bbox = extract_bbox_as_tensor(json_data)
    #print(tensor_bbox.tolist())

    # Save the tensor image to a file
    #output_image_path = ASSET_PATH + f'/output_image_{i}.png'
    #save_tensor_as_image(tensor_bbox, output_image_path)
    
    object_name = json_file.split('.')[0]
    object_patterns[object_name] = tensor_bbox.tolist()

# Save ALL object patterns
with open(ASSET_PATH + '/../all_object_patterns.json', 'w') as json_file:
    json.dump(object_patterns, json_file)
import os
import json
from PIL import Image
import torch
import numpy as np

ASSET_PATH = "src/gaming_slm/games/super_mario/assets"

def list_all_json_files(folder_path):
    json_file_list = []
    
    # Iterate over all files in the directory
    for filename in os.listdir(folder_path):
        if filename.endswith('.json'):
            json_file_list.append(filename)
    
    return json_file_list

def extract_bbox_as_tensor(json_data):

    # Decode image data
    image = Image.open(ASSET_PATH+'/screenshot/'+json_data['imagePath'])
    
    # Get bbox coordinates from points
    points = json_data['shapes'][0]['points']
    x1, y1 = points[0]
    x2, y2 = points[1]
    
    # Calculate top-left and bottom-right coordinates
    left = int(min(x1, x2))
    upper = int(min(y1, y2))
    right = int(max(x1, x2))
    lower = int(max(y1, y2))
    
    # Crop the region
    cropped_img = image.crop((left, upper, right, lower))
    
    # Convert image data to torch tensor
    tensor_img = torch.from_numpy(np.array(cropped_img)).float() / 255.0  # Normalize pixel values to [0, 1]
    
    # Change channel order (HWC -> CHW)
    tensor_img = tensor_img.permute(2, 0, 1)
    
    return tensor_img

def save_tensor_as_image(tensor_img, output_path):
    # Change channel order back to HWC
    img_array = tensor_img.permute(1, 2, 0).numpy() * 255.0
    img_array = img_array.astype(np.uint8)
    
    # Convert to PIL Image
    img = Image.fromarray(img_array)
    
    # Save image
    img.save(output_path)


# Get JSON files
json_data_list = list_all_json_files(ASSET_PATH)
print(json_data_list)


object_patterns = {}
for i, json_file in enumerate(json_data_list):

    # Load JSON data
    file_path = f'{ASSET_PATH}/{json_file}'
    with open(file_path, 'r') as f:
        json_data = json.load(f)

    # Call the function to get the image tensor
    tensor_bbox = extract_bbox_as_tensor(json_data)
    #print(tensor_bbox.tolist())

    # Save the tensor image to a file
    output_image_path = ASSET_PATH + f'/output_image_{i}.png'
    save_tensor_as_image(tensor_bbox, output_image_path)
    
    object_name = json_file.split('.')[0]
    object_patterns[object_name] = tensor_bbox.tolist()

# Save ALL object patterns
with open(ASSET_PATH + '/../all_object_patterns.json', 'w') as json_file:
    json.dump(object_patterns, json_file)