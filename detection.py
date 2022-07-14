import cv2
import os
import numpy as np
import json
from detectron2.structures import BoxMode
from detectron2.data import DatasetCatalog, MetadataCatalog
from detectron2 import model_zoo
from detectron2.engine import DefaultTrainer, DefaultPredictor
from detectron2.config import get_cfg
from detectron2.utils.visualizer import ColorMode, Visualizer

# Reading Json Data
def get_data_dicts(directory, classes):
    dataset_dicts = []
    for filename in [file for file in os.listdir(directory) if file.endswith('.json')]:
        json_file = os.path.join(directory, filename)
        with open(json_file) as f:
            img_anns = json.load(f)

        record = {}
        filename = os.path.join(directory, img_anns["imagePath"])
        
        record["file_name"] = filename    
        annos = img_anns["shapes"]
        objs = []
        for anno in annos:
            px = [a[0] for a in anno['points']] # x coord
            py = [a[1] for a in anno['points']] # y-coord
            poly = [(x, y) for x, y in zip(px, py)] # poly for segmentation
            poly = [p for x in poly for p in x]

            obj = {
                "bbox": [np.min(px), np.min(py), np.max(px), np.max(py)],
                "bbox_mode": BoxMode.XYXY_ABS,
                "segmentation": [poly],
                "category_id":0,

                # "category_id": classes.index(anno['label']),
                "iscrowd": 0
            }
            objs.append(obj)
        record["annotations"] = objs
        dataset_dicts.append(record)
    return dataset_dicts


# Define class from labels and dir where test and train is stored 
classes = ['stop_sign']
data_path = './data/'

for d in ["train", "test"]:
    DatasetCatalog.register(
        "category_" + d, 
        lambda d=d: get_data_dicts(data_path+d, classes)
    )
    
    MetadataCatalog.get("category_" + d).set(thing_classes=classes)

microcontroller_metadata = MetadataCatalog.get("category_train")

# Model values, increase "cfg.SOLVER.MAX_ITER" for more training 
cfg = get_cfg()
cfg.merge_from_file(model_zoo.get_config_file("COCO-InstanceSegmentation/mask_rcnn_R_50_FPN_3x.yaml"))
cfg.DATASETS.TRAIN = ("category_train",)
cfg.DATASETS.TEST = ()
cfg.DATALOADER.NUM_WORKERS = 2
cfg.MODEL.WEIGHTS = model_zoo.get_checkpoint_url("COCO-InstanceSegmentation/mask_rcnn_R_50_FPN_3x.yaml")
cfg.SOLVER.IMS_PER_BATCH = 4
cfg.SOLVER.BASE_LR = 0.00025
cfg.SOLVER.MAX_ITER = 1000
cfg.MODEL.ROI_HEADS.NUM_CLASSES = 1

# Create dir for model
os.makedirs(cfg.OUTPUT_DIR, exist_ok=True)
trainer = DefaultTrainer(cfg) 
trainer.resume_or_load(resume=False)

#Train model (comment out/in)
# trainer.train()

# Save model
cfg.OUTPUT_DIR = "./output/"
cfg.MODEL.WEIGHTS = os.path.join(cfg.OUTPUT_DIR, "model_final.pth")
cfg.MODEL.ROI_HEADS.SCORE_THRESH_TEST = 0.9  # set the testing threshold for this model
cfg.DATASETS.TEST = ("skin_test", )
predictor = DefaultPredictor(cfg)

# Image detection functions
def detect_signs(frame):   
    outputs = predictor(frame)
    v = Visualizer(frame[:, :, ::-1],
                       metadata=microcontroller_metadata, 
                       scale=1,
                       instance_mode=ColorMode.SEGMENTATION)

    mask_array = outputs['instances'].pred_masks.to("cpu").numpy()
    num_instances = mask_array.shape[0]
    mask_array = np.moveaxis(mask_array, 0, -1)

    mask_array_instance = []
    img = np.zeros_like(frame) #Black
    h = img.shape[0]
    w = img.shape[1]
    img_mask = np.zeros([h, w, 3], np.uint8)

    #Pred mask colors
    color = (0, 0, 255)

    #Pred scores
    score = outputs['instances'].scores.to("cpu").numpy()
    scores = []

    for score in score:
        scores.append(round(score*100))

    white_cords = []
 
    for i in range(num_instances):
        mask_array_instance.append(mask_array[:, :, i:(i+1)])
        img2 = np.where(mask_array_instance[i] == True, 255, img)
        array_img = np.asarray(img2)
        number_of_white_pix = np.sum(array_img == 255)
        whites = np.argwhere(array_img == 255)
        white_cords.append(whites)
        x_vals = []
        
        for i in range(len(whites)):
            x_vals.append(int(whites[i][1]))
     
        # Color for img overlay
        color = (200,200,200)
        img_mask[np.where((array_img==[255,255,255]).all(axis=2))] = color
        
    # Copies of images to combine overlay of detection pixels
    overlay = frame.copy()
    output = frame.copy()

    #draw box 
    img_mask = np.asarray(img_mask)
    output = cv2.addWeighted(img_mask, 1, overlay, 1, 0) 
    return output, scores, mask_array, white_cords

# Test from detection file (comment in/out below)

# # Choose file from "test_imgs"
# filename = "test1.jpg"
# img = cv2.imread("./test_imgs/"+filename)

# # Run detection 
# detection = detect_signs(img)

# output = detection[0]

# # Show, write img
# cv2.imshow("img", output)
# cv2.imwrite("detection.jpg", output)
# cv2.waitKey(0)
# cv2.destroyAllWindows()
 