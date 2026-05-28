/**
 * FASHN AI Virtual Try-On Example
 * Demonstrates how to use the Virtual Try-On v1.6 API with JavaScript
 */

import { fal } from "@fal-ai/client";
import dotenv from "dotenv";
import fs from "fs";

// Load environment variables
dotenv.config();

// Configure fal.ai client
fal.config({
  credentials: process.env.FAL_KEY || process.env.FASHN_API_KEY
});

/**
 * Perform virtual try-on using FASHN API
 * @param {string} modelImageUrl - URL of the model/person image
 * @param {string} garmentImageUrl - URL of the garment image
 * @param {Object} options - Optional parameters
 * @returns {Promise<Object>} Result with images array
 */
async function virtualTryon(modelImageUrl, garmentImageUrl, options = {}) {
  const input = {
    model_image: modelImageUrl,
    garment_image: garmentImageUrl,
    category: options.category || "auto",
    mode: options.mode || "balanced",
    garment_photo_type: options.garmentPhotoType || "auto",
    num_samples: options.numSamples || 1,
    output_format: options.outputFormat || "png",
    segmentation_free: options.segmentationFree ?? true,
  };

  // Add optional seed for reproducibility
  if (options.seed !== undefined) {
    input.seed = options.seed;
  }

  const result = await fal.subscribe("fal-ai/fashn/tryon/v1.6", {
    input,
    logs: true,
    onQueueUpdate: (update) => {
      if (update.status === "IN_PROGRESS") {
        update.logs?.map((log) => log.message).forEach(console.log);
      }
    },
  });

  return result;
}

/**
 * Submit async request with webhook
 * @param {string} modelImageUrl
 * @param {string} garmentImageUrl
 * @param {string} webhookUrl - URL to receive results
 * @returns {Promise<string>} Request ID
 */
async function submitAsync(modelImageUrl, garmentImageUrl, webhookUrl) {
  const { request_id } = await fal.queue.submit("fal-ai/fashn/tryon/v1.6", {
    input: {
      model_image: modelImageUrl,
      garment_image: garmentImageUrl,
    },
    webhookUrl,
  });

  return request_id;
}

/**
 * Check status of async request
 * @param {string} requestId
 * @returns {Promise<Object>} Status object
 */
async function checkStatus(requestId) {
  return await fal.queue.status("fal-ai/fashn/tryon/v1.6", {
    requestId,
    logs: true,
  });
}

/**
 * Get result of async request
 * @param {string} requestId
 * @returns {Promise<Object>} Result with images
 */
async function getResult(requestId) {
  return await fal.queue.result("fal-ai/fashn/tryon/v1.6", {
    requestId,
  });
}

/**
 * Download image from URL
 * @param {string} url - Image URL
 * @param {string} outputPath - Local file path
 */
async function downloadImage(url, outputPath) {
  const response = await fetch(url);
  const buffer = await response.arrayBuffer();
  fs.writeFileSync(outputPath, Buffer.from(buffer));
  console.log(`Image saved to: ${outputPath}`);
}

// Main example
async function main() {
  const MODEL_IMAGE = "https://storage.googleapis.com/falserverless/example_inputs/model.png";
  const GARMENT_IMAGE = "https://storage.googleapis.com/falserverless/example_inputs/garment.webp";

  console.log("Starting virtual try-on...");
  console.log(`Model: ${MODEL_IMAGE}`);
  console.log(`Garment: ${GARMENT_IMAGE}`);
  console.log();

  try {
    const result = await virtualTryon(MODEL_IMAGE, GARMENT_IMAGE, {
      category: "auto",
      mode: "balanced", // Options: performance, balanced, quality
    });

    console.log("Success!");
    console.log(`Generated ${result.images.length} image(s)`);

    result.images.forEach((image, i) => {
      console.log(`  Image ${i + 1}: ${image.url}`);

      // Optionally download the image
      // await downloadImage(image.url, `output_${i}.png`);
    });

  } catch (error) {
    console.error("Error:", error.message);
    if (error.response) {
      console.error("Response:", await error.response.text());
    }
  }
}

main();
