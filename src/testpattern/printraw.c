/*
 * 5-Channel TIFF to Raw Printer Data Converter
 *
 * This program reads a 5-channel TIFF file and converts it to raw printer
 * commands using Gutenprint's dithering and rasterization engine.
 * It feeds 8-bit channel data directly to the Raw input mode, allowing
 * DeviceN printing with full dithering.
 *
 * It expects the TIFF to be CMYKk.
 */

#include <gutenprint/gutenprint-intl.h>
#include <gutenprint/gutenprint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <tiffio.h>
#include <unistd.h>

#define NUM_CHANNELS 5

static FILE *output = NULL;
static const char *global_printer = NULL;

// Only keep TIFF and Gutenprint globals
static TIFF *input_tiff = NULL;
static uint32_t tiff_width = 0;
static uint32_t tiff_height = 0;
static uint16_t samples_per_pixel = 0;
static unsigned char *tiff_scanline = NULL;
static size_t tiff_scanline_size = 0;
static const char *input_filename = NULL;

static int Image_is_valid = 0;

static void writefunc(void *file, const char *buf, size_t bytes) {
  FILE *prn = (FILE *)file;
  if (!file)
    return;
  fwrite(buf, 1, bytes, prn);
}

// TIFF row callback for Gutenprint
static stp_image_status_t Image_get_row(stp_image_t *image, unsigned char *data,
                                        size_t byte_limit, int row) {
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
  // The TIFF is CMYKk, but the printer expects KCMYk, so we reorder the
  // channels. CMYKk -> kCMYk
  for (int i = 0; i < tiff_width; i++) {
    unsigned char k = tiff_scanline[i * NUM_CHANNELS + 3];
    unsigned char c = tiff_scanline[i * NUM_CHANNELS + 0];
    unsigned char m = tiff_scanline[i * NUM_CHANNELS + 1];
    unsigned char y = tiff_scanline[i * NUM_CHANNELS + 2];
    // Reorder to KCMYk
    tiff_scanline[i * NUM_CHANNELS + 0] = k; // K
    tiff_scanline[i * NUM_CHANNELS + 1] = c; // C
    tiff_scanline[i * NUM_CHANNELS + 2] = m; // M
    tiff_scanline[i * NUM_CHANNELS + 3] = y; // Y
  }
  memcpy(data, tiff_scanline, tiff_width * NUM_CHANNELS);
  return STP_IMAGE_STATUS_OK;
}

static int Image_width(stp_image_t *image) {
  (void)image;
  return tiff_width;
}
static int Image_height(stp_image_t *image) {
  (void)image;
  return tiff_height;
}
static void Image_init(stp_image_t *image) {
  (void)image;
  Image_is_valid = 1;
}
static void Image_reset(stp_image_t *image) { (void)image; }
static void Image_conclude(stp_image_t *image) {
  (void)image;
  Image_is_valid = 0;
}
static const char *Image_get_appname(stp_image_t *image) {
  (void)image;
  return "TIFF Raw Print";
}

static stp_image_t theImage = {Image_init,     Image_reset,   Image_width,
                               Image_height,   Image_get_row, Image_get_appname,
                               Image_conclude, NULL};

static void list_params(const stp_vars_t *v) {
  const stp_parameter_list_t *params = stp_get_parameter_list(v);
  int count = stp_parameter_list_count(params);
  for (int i = 0; i < count; i++) {
    const stp_parameter_t *p = stp_parameter_list_param(params, i);
    if (p->p_type == STP_PARAMETER_TYPE_STRING_LIST) {
      const char *val = stp_get_string_parameter(v, p->name);
      fprintf(stderr, "Parameter %s: %s\n", p->name, val ? val : "(null)");
    } else if (p->p_type == STP_PARAMETER_TYPE_INT &&
               stp_check_int_parameter(v, p->name, STP_PARAMETER_ACTIVE)) {
      int val = stp_get_int_parameter(v, p->name);
      fprintf(stderr, "Parameter %s: %d\n", p->name, val);
    } else if (p->p_type == STP_PARAMETER_TYPE_BOOLEAN &&
               stp_check_boolean_parameter(v, p->name, STP_PARAMETER_ACTIVE)) {
      int val = stp_get_boolean_parameter(v, p->name);
      fprintf(stderr, "Parameter %s: %s\n", p->name, val ? "true" : "false");
    } else if (p->p_type == STP_PARAMETER_TYPE_CURVE &&
               stp_check_curve_parameter(v, p->name, STP_PARAMETER_ACTIVE)) {
      // const stp_curve_t *val = stp_get_curve_parameter(v, p->name);
      // fprintf(stderr, "Parameter %s: Curve with %d points\n", p->name,
      // stp_curve_get_points(val));
    } else if (p->p_type == STP_PARAMETER_TYPE_DOUBLE &&
               stp_check_float_parameter(v, p->name, STP_PARAMETER_ACTIVE)) {
      double val = stp_get_float_parameter(v, p->name);
      fprintf(stderr, "Parameter %s: %f\n", p->name, val);
    }
  }
}

int main(int argc, char **argv) {
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
    fprintf(stderr, "Expected %d channels, got %d\n", NUM_CHANNELS,
            samples_per_pixel);
    TIFFClose(input_tiff);
    return 1;
  }
  tiff_scanline_size = TIFFScanlineSize(input_tiff);
  if (tiff_scanline_size == 0) {
    fprintf(stderr, "Cannot determine scanline size for TIFF\n");
    TIFFClose(input_tiff);
    return 1;
  }

  // sanity check: scanline size should be tiff_width * NUM_CHANNELS
  if (tiff_scanline_size != tiff_width * NUM_CHANNELS) {
    fprintf(stderr, "Scanline size mismatch: expected %zu, got %zu\n",
            (size_t)tiff_width * NUM_CHANNELS, tiff_scanline_size);
    TIFFClose(input_tiff);
    return 1;
  }

  tiff_scanline = malloc(tiff_scanline_size);
  if (!tiff_scanline) {
    fprintf(stderr, "Cannot allocate scanline buffer\n");
    TIFFClose(input_tiff);
    return 1;
  }
  stp_init();

  // set locale to C for consistent number formatting
  setlocale(LC_ALL, "C");

  output = stdout;
  stp_vars_t *v = stp_vars_create();
  const stp_printer_t *the_printer = stp_get_printer_by_driver(global_printer);
  if (!the_printer) {
    int j;
    fprintf(stderr, "Unknown printer %s\nValid printers are:\n",
            global_printer);
    for (j = 0; j < stp_printer_model_count(); j++) {
      the_printer = stp_get_printer_by_index(j);
      fprintf(stderr, "%-16s%s\n", stp_printer_get_driver(the_printer),
              stp_printer_get_long_name(the_printer));
    }
    return 1;
  }
  stp_set_printer_defaults(v, the_printer);

  fprintf(stderr, "Printer defaults:\n");
  list_params(v);
  fprintf(stderr, "\n");

  stp_set_outfunc(v, writefunc);
  stp_set_errfunc(v, writefunc);
  stp_set_outdata(v, output);
  stp_set_errdata(v, stderr);
  // stp_set_string_parameter(v, "Resolution", "1440x1440ov");
  stp_set_string_parameter(v, "Resolution", "720sw");
  stp_set_string_parameter(v, "InputImageType", "Raw");
  stp_set_string_parameter(v, "ChannelBitDepth", "8");
  stp_set_string_parameter(v, "RawChannels", "5");
  stp_set_float_parameter(v, "Density", 1.0);
  stp_set_string_parameter(v, "Quality", "None");
  stp_set_string_parameter(v, "ImageType", "None");
  stp_set_string_parameter(v, "PageSize", "A4");

  stp_dimension_t left, top, bottom, right;
  stp_get_imageable_area(v, &left, &right, &bottom, &top);

  stp_set_top(v, top);
  stp_set_left(v, left);
  stp_set_width(v, right - left);
  stp_set_height(v, bottom - top);

  list_params(v);

  stp_print(v, &theImage);
  stp_vars_destroy(v);
  TIFFClose(input_tiff);
  free(tiff_scanline);
  return 0;
}
