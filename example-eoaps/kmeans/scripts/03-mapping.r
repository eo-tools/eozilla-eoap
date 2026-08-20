#  Copyright (c) 2026- by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.
library(terra)
library(tmap)

arguments <- commandArgs(TRUE)

input_raster <- arguments[1]

bname <- basename(input_raster)
oname <- regmatches(bname, regexpr(".+?(?=\\.)", bname, perl = TRUE))

cluster_results <- rast(input_raster)

t_obj <- tm_shape(cluster_results) +
  tm_raster(
    col.scale = tm_scale_categorical(),
    col.legend = tm_legend(
      title = "Classes",
      bg.alpha = 0.6,
      frame = FALSE
    )
  ) +
  tm_title("Classifcation Result Preview") +
  tm_graticules(labels.size = 0.7) +
  tm_compass(position = tm_pos_out()) +
  tm_minimap(position = tm_pos_out(pos.h = "right", pos.v = "bottom")) +
  tm_layout(scale = 1.0)

tmap_save(t_obj, filename = paste0(oname, "_preview.jpeg"), dpi = 200, width = 1200, units = "px")
