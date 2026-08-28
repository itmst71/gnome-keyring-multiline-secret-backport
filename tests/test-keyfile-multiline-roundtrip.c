/*
 * Minimal, non-secret regression reproducer for GNOME Keyring's textual
 * keyring writer.  Build normally to demonstrate the pre-fix failure, or
 * with -DUSE_ESCAPING_WRITER to demonstrate the corrected behavior.
 *
 * SPDX-License-Identifier: LGPL-2.0-or-later
 */
#include <glib.h>

static void
test_multiline_round_trip (void)
{
	GKeyFile *written = g_key_file_new ();
	GKeyFile *reloaded = g_key_file_new ();
	GError *error = NULL;
	gchar *serialized;
	gsize serialized_length;

#ifdef USE_ESCAPING_WRITER
	g_key_file_set_string (written, "item", "secret", "first line\nsecond line\n");
#else
	g_key_file_set_value (written, "item", "secret", "first line\nsecond line\n");
#endif
	serialized = g_key_file_to_data (written, &serialized_length, &error);
	g_assert_no_error (error);
	g_assert_nonnull (serialized);

	g_assert_true (g_key_file_load_from_data (reloaded, serialized,
	                                           serialized_length,
	                                           G_KEY_FILE_NONE, &error));
	g_assert_no_error (error);

	g_free (serialized);
	g_key_file_unref (reloaded);
	g_key_file_unref (written);
}

int
main (int argc, char **argv)
{
	g_test_init (&argc, &argv, NULL);
	g_test_add_func ("/keyfile/multiline-secret-round-trip", test_multiline_round_trip);
	return g_test_run ();
}
