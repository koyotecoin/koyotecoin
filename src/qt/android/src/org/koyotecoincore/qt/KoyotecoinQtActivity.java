package org.koyotecoin.qt;

import android.os.Bundle;
import android.system.ErrnoException;
import android.system.Os;

import org.qtproject.qt5.android.bindings.QtActivity;

import java.io.File;

public class KoyotecoinQtActivity extends QtActivity
{
    @Override
    public void onCreate(Bundle savedInstanceState)
    {
        final File koyotecoinDir = new File(getFilesDir().getAbsolutePath() + "/.koyotecoin");
        if (!koyotecoinDir.exists()) {
            koyotecoinDir.mkdir();
        }

        super.onCreate(savedInstanceState);
    }
}
