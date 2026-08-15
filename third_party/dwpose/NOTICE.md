# DWPose third-party notice

`canvas_core/dwpose_inference.py` contains a modified, CPU-only adaptation of the
ONNX inference and pose-rendering examples from
[IDEA-Research/DWPose](https://github.com/IDEA-Research/DWPose), copyright 2023
IDEA. DWPose and the referenced MMPose portions are licensed under Apache-2.0.

Changes made for SHIYIN AI include removal of Torch, Matplotlib and CUDA runtime
requirements; lazy, thread-safe ONNX Runtime session management; explicit model
availability errors; RGB/BGR conversion; and integration with the persistent
model manager and desktop HTTP service.

The downloaded `yolox_l.onnx` and `dw-ll_ucoco_384.onnx` files are obtained from
the DWPose project distribution sources and are verified against fixed SHA-256
digests before use.
