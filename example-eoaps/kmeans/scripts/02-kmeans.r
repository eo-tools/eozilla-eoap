#  Copyright (c) 2026- by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.
library(terra)

args <- commandArgs(TRUE)

raster_stack <- args[1]
clusters <- as.integer(args[2])

bname <- basename(raster_stack)
oname <- regmatches(bname, regexpr(".+?(?=\\.)", bname, perl = TRUE))

raster <- rast(raster_stack)

clustered <- k_means(raster, centers = clusters)

writeRaster(clustered, paste0(oname, "_clustered.gtiff"), filetype = "GTiff")
