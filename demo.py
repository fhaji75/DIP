# Copyright (c) Facebook, Inc. and its affiliates. All Rights Reserved
import argparse
import glob
import multiprocessing as mp
import os
import time
import cv2
import tqdm

from detectron2.config import get_cfg
from detectron2.data.detection_utils import read_image
from detectron2.utils.logger import setup_logger
from predictor import VisualizationDemo

# constants
WINDOW_NAME = "COCO detections"


def setup_cfg(args):
    # load config from file and command-line arguments
    cfg = get_cfg()
    from projects.SparseRCNN.sparsercnn import add_sparsercnn_config
    add_sparsercnn_config(cfg)
    cfg.merge_from_file(args.config_file)
    cfg.merge_from_list(args.opts)
    # Set score_threshold for builtin models
    cfg.MODEL.RETINANET.SCORE_THRESH_TEST = args.confidence_threshold
    cfg.MODEL.ROI_HEADS.SCORE_THRESH_TEST = args.confidence_threshold
    cfg.MODEL.PANOPTIC_FPN.COMBINE.INSTANCES_CONFIDENCE_THRESH = args.confidence_threshold
    cfg.freeze()
    return cfg


def get_parser():
    parser = argparse.ArgumentParser(description="Detectron2 demo for builtin models")
    parser.add_argument(
        "--config-file",
        default="configs/quick_schedules/mask_rcnn_R_50_FPN_inference_acc_test.yaml",
        metavar="FILE",
        help="path to config file",
    )
    parser.add_argument("--webcam", action="store_true", help="Take inputs from webcam.")
    parser.add_argument("--video-input", help="Path to video file.")
    parser.add_argument(
        "--input",
        nargs="+",
        help="A list of space separated input images; "
        "or a single glob pattern such as 'directory/*.jpg'",
    )
    parser.add_argument(
        "--output",
        help="A file or directory to save output visualizations. "
        "If not given, will show output in an OpenCV window.",
    )

    parser.add_argument(
        "--confidence-threshold",
        type=float,
        default=0.5,
        help="Minimum score for instance predictions to be shown",
    )
    parser.add_argument(
        "--opts",
        help="Modify config options using the command-line 'KEY VALUE' pairs",
        default=[],
        nargs=argparse.REMAINDER,
    )
    return parser


if __name__ == "__main__":
    mp.set_start_method("spawn", force=True)
    args = get_parser().parse_args()
    setup_logger(name="fvcore")
    logger = setup_logger()
    logger.info("Arguments: " + str(args))

    cfg = setup_cfg(args)

    demo = VisualizationDemo(cfg)

    if args.input:
        if len(args.input) == 1:
            args.input = glob.glob(os.path.expanduser(args.input[0]))
            assert args.input, "The input path(s) was not found"
        for path in tqdm.tqdm(args.input, disable=not args.output):
            # use PIL, to be consistent with evaluation
            #img = read_image(path, format="BGR")
            # SparseRCNN uses RGB input as default 
            img = read_image(path, format="RGB")
            start_time = time.time()
            predictions, visualized_output = demo.run_on_image(img, args.confidence_threshold)
            
            file_name = ''
            for i in range(len(path)):
              if path[len(path)-1-i]!='/':
                file_name = file_name + path[len(path)-1-i]
              else :
                break  
            file_name = file_name[::-1]   
            img1 = cv2.GaussianBlur(img,(3, 3), 0);
            edg_img = cv2.Canny(img1,100,200)
            grad_x = cv2.Sobel(edg_img,cv2.CV_16S,1,0)
            grad_y = cv2.Sobel(edg_img,cv2.CV_16S,0,1)
            direction = np.arctan2(grad_y,grad_x)
            result_model = []
            for  b in range(len(predictions["instances"].pred_boxes)):
              x0= predictions["instances"].pred_boxes.tensor[b][0]
              y0=predictions["instances"].pred_boxes.tensor[b][1]
              x1=predictions["instances"].pred_boxes.tensor[b][2]
              y1=predictions["instances"].pred_boxes.tensor[b][3]
              #x0 = predictions[b][0]
              #y0 = predictions[b][1]
              #x1 = predictions[b][2]
              #y1 = predictions[b][3]
              x_intersection = int((x0+x1)/2)
              y_intersection = int((y0+y1)/2)
              hist = {}
              for i in range(x_intersection-10,x_intersection+10):
                for j in range(y_intersection-10,y_intersection+10):
                  if i <1296 and j <976 and i>=0 and j >=0:
                    grad_mag = np.sqrt((grad_x[j][i]**2)+(grad_y[j][i]**2))
                    if abs(grad_mag) > 100:
                      flag = 0
                      for k in (hist.keys()):
                        if k == direction[j][i]:
                          hist[k] = hist[k] + 1
                          flag = 1
                          break
                      if flag == 0:
                        hist[direction[j][i]] = 1
                  
              max_d = 0
              max_direct = 0    
              for k in  (hist.keys()):
                if hist[k] > max_d:
                  max_direct = k
                  max_d = hist[k]

              angle_point =max_direct
              angle_result = (angle_point *180)/np.pi
              result_model.append([x_intersection,y_intersection,angle_result])
            #csv
            file_name = file_name[:len(file_name)-3]
            import csv
            #file_name='/content/drive/MyDrive/Final/SparseR-CNN/datasets/coco/output/'+file_name+'csv'
            file_name='.\SparseR-CNN\datasets\coco\output\'+file_name+'csv'
            #file_name = '.\\'+file_name+'csv'
            with open(file_name,'w', newline='') as csvfile :
                data = csv.writer(csvfile,delimiter = ',')
                for i in range(len(result_model)):
                    data.writerow(result_model[i])
            
                        
            logger.info(
                "{}: {} in {:.2f}s".format(
                    path,
                    "detected {} instances".format(len(predictions["instances"]))
                    if "instances" in predictions
                    else "finished",
                    time.time() - start_time,
                )
            )

            if args.output:
                if os.path.isdir(args.output):
                    assert os.path.isdir(args.output), args.output
                    out_filename = os.path.join(args.output, os.path.basename(path))
                else:
                    assert len(args.input) == 1, "Please specify a directory with args.output"
                    out_filename = args.output
                visualized_output.save(out_filename)
            else:
                cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)
                cv2.imshow(WINDOW_NAME, visualized_output.get_image()[:, :, ::-1])
                if cv2.waitKey(0) == 27:
                    break  # esc to quit

    elif args.webcam:
        assert args.input is None, "Cannot have both --input and --webcam!"
        assert args.output is None, "output not yet supported with --webcam!"
        cam = cv2.VideoCapture(0)
        for vis in tqdm.tqdm(demo.run_on_video(cam, args.confidence_threshold)):
            cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)
            cv2.imshow(WINDOW_NAME, vis)
            if cv2.waitKey(1) == 27:
                break  # esc to quit
        cam.release()
        cv2.destroyAllWindows()
    elif args.video_input:
        video = cv2.VideoCapture(args.video_input)
        width = int(video.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(video.get(cv2.CAP_PROP_FRAME_HEIGHT))
        frames_per_second = video.get(cv2.CAP_PROP_FPS)
        num_frames = int(video.get(cv2.CAP_PROP_FRAME_COUNT))
        basename = os.path.basename(args.video_input)

        if args.output:
            if os.path.isdir(args.output):
                output_fname = os.path.join(args.output, basename)
                output_fname = os.path.splitext(output_fname)[0] + ".mkv"
            else:
                output_fname = args.output
            assert not os.path.isfile(output_fname), output_fname
            output_file = cv2.VideoWriter(
                filename=output_fname,
                # some installation of opencv may not support x264 (due to its license),
                # you can try other format (e.g. MPEG)
                fourcc=cv2.VideoWriter_fourcc(*"x264"),
                fps=float(frames_per_second),
                frameSize=(width, height),
                isColor=True,
            )
        assert os.path.isfile(args.video_input)
        for vis_frame in tqdm.tqdm(demo.run_on_video(video, args.confidence_threshold), total=num_frames):
            if args.output:
                output_file.write(vis_frame)
            else:
                cv2.namedWindow(basename, cv2.WINDOW_NORMAL)
                cv2.imshow(basename, vis_frame)
                if cv2.waitKey(1) == 27:
                    break  # esc to quit
        video.release()
        if args.output:
            output_file.release()
        else:
            cv2.destroyAllWindows()
