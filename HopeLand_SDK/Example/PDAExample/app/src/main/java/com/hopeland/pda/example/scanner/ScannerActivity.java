package com.hopeland.pda.example.scanner;

import java.nio.charset.Charset;

import com.hopeland.pda.example.R;
import com.pda.scanner.ScanReader;
import com.pda.scanner.Scanner;
import com.port.Adapt;
import com.util.BaseActivity;

import android.content.DialogInterface;
import android.media.AudioManager;
import android.media.ToneGenerator;
import android.os.Bundle;
import android.os.Message;
import android.view.KeyEvent;
import android.view.View;
import android.view.WindowManager;
import android.widget.EditText;

public class ScannerActivity extends BaseActivity {
    boolean busy = false;

    static final int MSG_UPDATE_ID = MSG_USER_BEG + 1;

    //ScanReader object
    private static Scanner scanReader = ScanReader.getScannerInstance();

    //ToneGenerator beep
    ToneGenerator toneGenerator = new ToneGenerator(AudioManager.STREAM_SYSTEM,
            ToneGenerator.MAX_VOLUME);

    @Override
    public void msgProcess(Message msg) {
        switch (msg.what) {
            case MSG_UPDATE_ID:
                String idString = (String) msg.obj;
                EditText text = (EditText) findViewById(R.id.tb_txtRecv);
                text.setText(idString);
                break;
            default:
                super.msgProcess(msg);
                break;
        }
    }

    //
    protected void DeCode() {
        if (busy) {
            showTip(getString(R.string.str_busy));
            return;
        }

        busy = true;

        new Thread() {
            @Override
            public void run() {

                sendMessage(MSG_SHOW_WAIT,
                        getString(R.string.str_please_waitting));

                byte[] id = scanReader.decode();

                String idString;
                if (id != null) {

                    String utf8 = new String(id, Charset.forName("utf8"));

                    if (utf8.contains("\ufffd")) {
                        utf8 = new String(id, Charset.forName("gbk"));
                    }

                    idString = utf8 + "\n";
                    toneGenerator.startTone(ToneGenerator.TONE_PROP_BEEP);
                } else {
                    idString = null;
                    showTip(getString(R.string.str_faild));
                }

                sendMessage(MSG_UPDATE_ID, idString);
                sendMessage(MSG_HIDE_WAIT, null);

                busy = false;
            }

        }.start();

    }

    //Triger
    public void Triger(View v) {
        DeCode();
    }

    //back
    public void Back(View v) {
        scanReader.close();
        finish();
    }

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        getWindow().setFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON,
                WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        this.setContentView(R.layout.scan_main);

        showCustomBar(getString(R.string.btn_MainMenu_Scan),
                getString(R.string.str_back), null,
                R.drawable.left, 0,
                new View.OnClickListener() {
                    @Override
                    public void onClick(View v) {
                        Back(v);
                    }
                },
                null
        );
    }

    //Init
    protected void Init() {
        if (!scaninit()) { // Failed to open the module power supply
            showMsg(getString(R.string.scanner_open_power_faild),
                    new DialogInterface.OnClickListener() {
                        @Override
                        public void onClick(DialogInterface arg0, int arg1) {
                            finish();
                        }
                    });
            return;
        }
        scanReader.enableBlockScankey(false);

    }

    //Dispose
    protected void DeInit() {
        try {
            scanReader.enableBlockScankey(true);
            ScanDispose();
        } catch (Exception e) {}
    }

    //Turn on the module power
    private boolean scaninit() {
        if (null == scanReader) {
            return false;
        }

        return scanReader.open(getApplicationContext());
    }

    //Turn off module power
    private void ScanDispose() {
        scanReader.close();
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        DeInit();
    }

    @Override
    protected void onPause() {
        super.onPause();
        DeInit();
    }

    @Override
    protected void onResume() {
        super.onResume();
        Init();
    }

    //The key events
    @Override
    public boolean onKeyDown(int keyCode, android.view.KeyEvent event) {
        if (Adapt.DEVICE_TYPE_HY820 == Adapt.getDeviceType() && keyCode ==139||Adapt.DEVICE_TYPE_HY830 == Adapt.getDeviceType() && keyCode ==121) { // handle trigger button
            DeCode();
            return true;
        }

        return super.onKeyDown(keyCode, event);
    }

    ;
}
