# Architecture

## Pipeline Architecture

The system uses a high-performance pipeline for processing CAN frames:

DeviceReader → PacketDecoder → SharedRingBuffer → BatchBuilder → FrameDispatcher

## Signal Discovery Algorithms

Automatic discovery uses entropy, variance, and correlation analysis to identify signals without DBC files.

## ML Model Design

Models classify signal types and provide semantic inference for vehicle parameters.

## System Deployment Guide

1. Install dependencies: `pip install -r requirements.txt`
2. Run: `python main.py`
3. Configure via `configs/config.yaml`