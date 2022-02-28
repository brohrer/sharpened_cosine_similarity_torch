"""
Based on  and copy/pasted heavily from code
https://github.com/ZeWang95/scs_pytorch/blob/main/scs.py
from Ze Wang
https://twitter.com/ZeWang46564905/status/1488371679936057348?s=20&t=lB_T74PcwZmlJ1rrdu8tfQ

and code
https://github.com/oliver-batchelor/scs_cifar/blob/main/src/scs.py
from Oliver Batchelor
https://twitter.com/oliver_batch/status/1488695910875820037?s=20&t=QOnrCRpXpOuC0XHApi6Z7A

and the TensorFlow implementation
https://colab.research.google.com/drive/1Lo-P_lMbw3t2RTwpzy1p8h0uKjkCx-RB
and blog post
https://www.rpisoni.dev/posts/cossim-convolution/
from Raphael Pisoni
https://twitter.com/ml_4rtemi5

Check here to get the full story.
https://e2eml.school/scs.html
"""

import torch
from torch import nn
from torch.nn import functional as F


class CosSimConv2d(nn.Conv2d):
    def __init__(
        self,
        in_channels: int,
        out_channels: int,
        kernel_size,
        stride=1,
        padding=None,
        dilation=1,
        groups: int = 1,
        bias: bool = False,
        q_init: float = 10,
        p_init: float = 1.1,
        q_scale: float = .3,
        p_scale: float = 5,
    ):
        if padding is None:
            if int(torch.__version__.split('.')[1]) >= 10:
                padding = "same"
            else:
                # This doesn't support even kernels
                padding = ((stride - 1) + dilation * (kernel_size - 1)) // 2
        if isinstance(kernel_size, int):
            kernel_size = (kernel_size, kernel_size)

        bias = False  # Disable bias for "true" SCS, add it for better performance
        assert dilation == 1, "Dilation has to be 1 to use AvgPool2d as L2-Norm backend."
        assert groups == in_channels or groups == 1, "Either depthwise or full convolution. Grouped not supported"
        super(CosSimConv2d, self).__init__(
            in_channels,
            out_channels,
            kernel_size,
            stride,
            padding,
            dilation,
            groups,
            bias)
        self.q_scale = q_scale
        self.q = torch.nn.Parameter(torch.full((1,), q_init * self.q_scale))
        self.p_scale = p_scale
        self.p = torch.nn.Parameter(torch.full((1,), p_init * self.p_scale))

    def forward(self, inp: torch.Tensor) -> torch.Tensor:
        out = inp.square()
        if self.groups == 1:
            out = out.sum(1, keepdim=True)
        norm = F.conv2d(
            out,
            torch.ones_like(self.weight[:1, :1]),
            None,
            self.stride,
            self.padding,
            self.dilation) + 1e-6

        q = torch.exp(-self.q / self.q_scale)
        weight = self.weight / (
            self.weight.square().sum(dim=(1, 2, 3), keepdim=True).sqrt() + q)
        out = F.conv2d(
            inp,
            weight,
            self.bias,
            self.stride,
            self.padding,
            self.dilation,
            self.groups) / norm.sqrt()

        # Comment these lines out for vanilla cosine similarity.
        # It's ~200x faster.
        abs = (out.square() + 1e-6).sqrt()
        sign = out / abs
        p = torch.exp(self.p / self.p_scale)
        out = abs ** p
        out = out * sign
        return out
