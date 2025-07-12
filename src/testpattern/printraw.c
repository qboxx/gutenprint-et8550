/*
 * 5-Channel TIFF to Raw Printer Data Converter
 *
 * This program reads a 5-channel TIFF file and converts it to raw printer
 * commands using Gutenprint's dithering and rasterization engine.
 * It feeds 8-bit channel data directly to the Raw input mode, allowing
 * DeviceN printing with full dithering.
 */

#include <stdlib.h>
#include <unistd.h>
#include <stdio.h>
#include <string.h>
#include <tiffio.h>
#include <gutenprint/gutenprint.h>
#include <gutenprint/gutenprint-intl.h>

#define NUM_CHANNELS 5

static FILE *output = NULL;
static const char *global_printer = NULL;
static double global_density = 1.0;
static const char *global_image_type = "Raw";
static int global_bit_depth = 8;
static int global_channel_depth = NUM_CHANNELS;

// Only keep TIFF and Gutenprint globals
static TIFF *input_tiff = NULL;
static uint32_t tiff_width = 0;
static uint32_t tiff_height = 0;
static uint16_t samples_per_pixel = 0;
static unsigned char *tiff_scanline = NULL;
static const char *input_filename = NULL;

static int Image_is_valid = 0;

static void writefunc(void *file, const char *buf, size_t bytes)
{
  FILE *prn = (FILE *)file;
  if (!file) return;
  fwrite(buf, 1, bytes, prn);
}

static void close_output(void)
{
  if (output && output != stdout)
  {
    fclose(output);
    output = NULL;
  }
}

// TIFF row callback for Gutenprint
static stp_image_status_t Image_get_row(stp_image_t *image, unsigned char *data, size_t byte_limit, int row)
{
    (void)image;
    (void)byte_limit;
    if (!Image_is_valid) {
        fputs("Calling Image_get_row with invalid image!\n", stderr);
        abort();
    }
    if (TIFFReadScanline(input_tiff, tiff_scanline, row, 0) < 0) {
        fprintf(stderr, "Failed to read row %d from TIFF\n", row);
        return STP_IMAGE_STATUS_ABORT;
    }
    memcpy(data, tiff_scanline, tiff_width * NUM_CHANNELS);
    return STP_IMAGE_STATUS_OK;
}

static int Image_width(stp_image_t *image) { (void)image; return tiff_width; }
static int Image_height(stp_image_t *image) { (void)image; return tiff_height; }
static void Image_init(stp_image_t *image) { (void)image; Image_is_valid = 1; }
static void Image_reset(stp_image_t *image) { (void)image; }
static void Image_conclude(stp_image_t *image) { (void)image; Image_is_valid = 0; }
static const char *Image_get_appname(stp_image_t *image) { (void)image; return "TIFF Raw Print"; }

static stp_image_t theImage = {
    Image_init,
    Image_reset,
    Image_width,
    Image_height,
    Image_get_row,
    Image_get_appname,
    Image_conclude,
    NULL
};

int main(int argc, char **argv)
{
    if (argc < 3) {
        fprintf(stderr, "Usage: %s <printer-driver> <tiff-file>\n", argv[0]);
        return 1;
    }
    global_printer = argv[1];
    input_filename = argv[2];
    input_tiff = TIFFOpen(input_filename, "r");
    if (!input_tiff) {
        fprintf(stderr, "Cannot open TIFF file: %s\n", input_filename);
        return 1;
    }
    TIFFGetField(input_tiff, TIFFTAG_IMAGEWIDTH, &tiff_width);
    TIFFGetField(input_tiff, TIFFTAG_IMAGELENGTH, &tiff_height);
    TIFFGetField(input_tiff, TIFFTAG_SAMPLESPERPIXEL, &samples_per_pixel);
    if (samples_per_pixel != NUM_CHANNELS) {
        fprintf(stderr, "Expected %d channels, got %d\n", NUM_CHANNELS, samples_per_pixel);
        TIFFClose(input_tiff);
        return 1;
    }
    tiff_scanline = malloc(TIFFScanlineSize(input_tiff));
    if (!tiff_scanline) {
        fprintf(stderr, "Cannot allocate scanline buffer\n");
        TIFFClose(input_tiff);
        return 1;
    }
    stp_init();
    output = stdout;
    stp_vars_t *v = stp_vars_create();
    const stp_printer_t *the_printer = stp_get_printer_by_driver(global_printer);
    if (!the_printer) {
      int j;
      fprintf(stderr, "Unknown printer %s\nValid printers are:\n",
	      global_printer);
      for (j = 0; j < stp_printer_model_count(); j++)
	{
	  the_printer = stp_get_printer_by_index(j);
	  fprintf(stderr, "%-16s%s\n", stp_printer_get_driver(the_printer),
		  stp_printer_get_long_name(the_printer));
	}
      return 1;
    }
    stp_set_printer_defaults(v, the_printer);
    stp_set_outfunc(v, writefunc);
    stp_set_errfunc(v, writefunc);
    stp_set_outdata(v, output);
    stp_set_errdata(v, stderr);
    stp_set_string_parameter(v, "InputImageType", global_image_type);
    stp_set_string_parameter(v, "ChannelBitDepth", "8");
    stp_set_string_parameter(v, "RawChannels", "5");
    stp_set_float_parameter(v, "Density", global_density);
    stp_set_string_parameter(v, "Quality", "None");
    stp_set_string_parameter(v, "ImageType", "None");
    stp_set_width(v, tiff_width);
    stp_set_height(v, tiff_height);
    stp_print(v, &theImage);
    stp_vars_destroy(v);
    TIFFClose(input_tiff);
    free(tiff_scanline);
    return 0;
}
