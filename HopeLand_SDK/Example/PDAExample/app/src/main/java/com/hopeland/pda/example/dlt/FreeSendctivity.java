package com.hopeland.pda.example.dlt;

import android.content.res.Configuration;
import android.os.Bundle;
import android.os.Message;
import android.util.Log;
import android.view.View;
import android.view.ViewGroup;
import android.view.WindowManager;
import android.widget.AdapterView;
import android.widget.AdapterView.OnItemSelectedListener;
import android.widget.ArrayAdapter;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.Spinner;
import android.widget.TextView;

import com.pda.com.COM;
import com.pda.com.COMReader;
import com.hopeland.pda.example.R;
import com.port.Adapt;
import com.util.Helper.Helper_String;
import com.util.BaseActivity;

import java.util.ArrayList;
import java.util.List;

public class FreeSendctivity extends BaseActivity {

	COM com = null;

	TextView textSend = null;
	TextView textRecv = null;
	Button btnOpen = null;
	Button btnWork = null;
	Spinner spinnerPort = null;
	Spinner spinnerSpeed = null;
	Spinner spinnerParity = null;
	Spinner spinnerMode = null;

	byte[] recv = new byte[1024];
	int recvlen = 0;

	static final int MSG_REFLESH = MSG_USER_BEG + 1;
	static final int MSG_WORKED = MSG_USER_BEG + 2;
	static final int MSG_STOPED = MSG_USER_BEG + 3;

	@Override
	protected void msgProcess(Message msg) {
		switch (msg.what) {
		case MSG_REFLESH:
			String recv = (String) msg.obj;
			textRecv.setText(recv);
			break;
		case MSG_WORKED:
			worked = true;
			btnWork.setText(getString(R.string.str_btn_com_stop));
			break;
		case MSG_STOPED:
			worked = false;
			btnWork.setText(getString(R.string.str_btn_com_work));
			break;
		default:
			super.msgProcess(msg);
			break;
		}
	}

	@Override
	protected void onCreate(Bundle savedInstanceState) {

		super.onCreate(savedInstanceState);
		setContentView(R.layout.dlt_free_send);
		ChangeLayout(getResources().getConfiguration());

		List<String> portList = new ArrayList<String>();
		
		if (Adapt.getPropertiesInstance().support("IRDA")) {
			portList.add("IRDA");
		}
		if (Adapt.getPropertiesInstance().support("LaserIRDA")) {
			portList.add("LaserIRDA");
		}
		if (Adapt.getPropertiesInstance().support("RS232")) {
			portList.add("RS232");
		}
		if (Adapt.getPropertiesInstance().support("RS485")) {
			portList.add("RS485");
		}
		if (Adapt.getPropertiesInstance().support("ESAM")) {
			portList.add("ESAM");
		}
		if (Adapt.getPropertiesInstance().support("RESAM")) {
			portList.add("RESAM");
		}
		
		String[] portStringArray = new String[portList.size()];
		portStringArray =  (String[]) portList.toArray(portStringArray);

		textSend = (TextView) findViewById(R.id.tb_com_send);
		textRecv = (TextView) findViewById(R.id.tb_com_recv);

		btnOpen = (Button) findViewById(R.id.btn_com_open);
		btnWork = (Button) findViewById(R.id.btn_com_work);

		spinnerPort = (Spinner) findViewById(R.id.sp_com_com);
		spinnerSpeed = (Spinner) findViewById(R.id.sp_com_speed);
		spinnerParity = (Spinner) findViewById(R.id.sp_com_parity);
		spinnerMode = (Spinner) findViewById(R.id.sp_com_mode);
		spinnerPort.setOnItemSelectedListener(new OnItemSelectedListener() {

			@Override
			public void onItemSelected(AdapterView<?> parent, View view,
					int position, long id) {
				// TODO Auto-generated method stub
				String port = spinnerPort.getSelectedItem().toString();
				if ((port.equalsIgnoreCase("IRDA")) 
					|| (port.equalsIgnoreCase("LaserIRDA"))) {
					spinnerSpeed.setSelection(0);
					spinnerParity.setSelection(2);
					textSend.setText("FE FE 68 AA AA AA AA AA AA 68 13 00 DF 16 ");
				} else if ((port.equalsIgnoreCase("RS232"))
					|| (port.equalsIgnoreCase("RS485"))) {
					spinnerSpeed.setSelection(1);
					spinnerParity.setSelection(2);
					textSend.setText("FE FE 68 AA AA AA AA AA AA 68 13 00 DF 16 ");
				} else if (port.equalsIgnoreCase("ESAM")) {
					spinnerSpeed.setSelection(2);
					spinnerParity.setSelection(2);

					if (Adapt.getSN().toUpperCase().startsWith("G7N")) {
						spinnerParity.setSelection(2);
						spinnerSpeed.setSelection(4);
						textSend.setText("55 00 A2 01 02 00 01 08 57");
					} else {
						if (Adapt.getPropertiesInstance().getDeviceModel("ESAM").equals("SecurityUnit-2.0")) {
							if (Adapt.getPropertiesInstance().support("RESAM")) {    // 1.0版本 + RESAM
								textSend.setText("E9 00 02 00 10 FB E6");
							} else { // 2.0版本
								spinnerParity.setSelection(0);
								spinnerSpeed.setSelection(4);
								// textSend.setText("E9 00 02 00 01 EC E6");
								textSend.setText("E9 00 04 01 01 01 08 F8 E6");
							}
						} else { // 1.0版本
							textSend.setText("E9 00 02 00 10 FB E6");
						}
					}
				} else if (port.equalsIgnoreCase("RESAM")) {
					spinnerSpeed.setSelection(2);
					spinnerParity.setSelection(2);
					textSend.setText("55 90 46 00 FF 00 00 D6");
				}
				sendMessage(MSG_REFLESH, "");

			}

			@Override
			public void onNothingSelected(AdapterView<?> parent) {
				// TODO Auto-generated method stub
				
			}
		});
		ArrayAdapter<String> portAdapter = new ArrayAdapter<String>(this,
				android.R.layout.simple_spinner_item, portStringArray);
		spinnerPort.setAdapter(portAdapter);
		try {
			getWindow().setFlags(
					WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON,
					WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
		} catch (Exception ex) {
			Log.d("Debug", "The initialization of abnormal:" + ex.getMessage());
		}

		showCustomBar(getString(R.string.STR_FREE_SEND),
				getString(R.string.str_back), null,
				R.drawable.left, 0,
				new View.OnClickListener() {
					@Override
					public void onClick(View v) {
						onClose(v);
					}
				},
				null
		);

	}

	private void ChangeLayout(Configuration newConfig) {
		LinearLayout main = (LinearLayout)findViewById(R.id.view_split_main);
		LinearLayout left = (LinearLayout)findViewById(R.id.view_split_left);
		LinearLayout right = (LinearLayout)findViewById(R.id.view_split_right);

		if (newConfig.orientation == Configuration.ORIENTATION_LANDSCAPE) { //当前屏幕为横屏
			main.setOrientation(LinearLayout.HORIZONTAL);

			LinearLayout.LayoutParams leftParam = new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, (float) 0.5);
			LinearLayout.LayoutParams rightParam = new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.MATCH_PARENT, (float) 0.5);

			leftParam.setMargins(0, 0, 10, 0);
			rightParam.setMargins(10, 0, 0, 0);

			left.setLayoutParams(leftParam);
			right.setLayoutParams(rightParam);

		} else { // 当前屏幕为竖屏
			main.setOrientation(LinearLayout.VERTICAL);

			LinearLayout.LayoutParams leftParam = new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
			LinearLayout.LayoutParams rightParam = (new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));

			leftParam.setMargins(0, 0, 0, 0);
			rightParam.setMargins(0, 0, 0, 0);

			left.setLayoutParams(leftParam);
			right.setLayoutParams(rightParam);
		}

	}

	@Override
	public void onConfigurationChanged(Configuration newConfig) {
		super.onConfigurationChanged(newConfig);
		ChangeLayout(newConfig);
	}

	@Override
	protected void onDestroy() {
		super.onDestroy();
		if (com != null) {
			com.close();
		}
		worked = false;
	}

	boolean worked = false;;
	boolean opend = false;

	public void sendOnetime(byte[] send)
	{
		com.clear_input();
		com.send(send);

		int wait = 100;
		int recvlen = 0;
		byte[] recv = new byte[16*1024];
		for (int i = 0; i < 3000; i += wait) {
			try {
				Thread.sleep(wait);
			} catch (InterruptedException e) {
				e.printStackTrace();
			}

			int count = com.recv(recv, recvlen, recv.length - recvlen);
			if (count > 0) {
				recvlen += count;
				if (recvlen >= recv.length) {
					break;
				}
			} else {
				if (recvlen > 0) {
					break;
				}
			}

		}

		String rString = null;
		if (recvlen > 0) {
			rString = Helper_String.Bytes2String(recv, 0, recvlen, " ");
		} else {
			rString = "";
		}

		sendMessage(MSG_REFLESH, rString);
		sendMessage(MSG_STOPED, null);
	}
	
	public void receiveLoop(byte[] send)
	{
		com.clear_input();
		//com.send(send);

		int wait = 100;
		int recvlen = 0;
		byte[] recv = new byte[16*1024];
		while (worked)
		{
			try {
				Thread.sleep(wait);
			} catch (InterruptedException e) {
				e.printStackTrace();
			}

			int count = com.recv(recv, recvlen, recv.length - recvlen);
			if (count > 0) {
				recvlen += count;
				String rString = Helper_String.Bytes2String(recv, 0, recvlen, " ");
				sendMessage(MSG_REFLESH, rString);
			}
		}

	}
	
	
	public void onWork(View v) {
		if (null == com) {
			return;
		}

		if (worked) {
			sendMessage(MSG_STOPED, null);
		} else {
			sendMessage(MSG_REFLESH, "");
			sendMessage(MSG_WORKED, null);

			String sendString = textSend.getText().toString();
			sendString = Helper_String.remove(sendString, ' ');
			final int mode = spinnerMode.getSelectedItemPosition();
	
			final byte[] send = Helper_String.hexStringToBytes(sendString);
	
			new Thread() {
				@Override
				public void run() {
					while (!worked) {
						try {
							Thread.sleep(10);
						} catch (InterruptedException e) {
						}
					}
					if (0 == mode) {
						sendOnetime(send);
					} else {
						receiveLoop(send);
					}
				}
			}.start();
		}
	}

	public void onOpen(View v) {
		if (isFastClick()) {
			return;
		}

		if (!opend) {

			String port = spinnerPort.getSelectedItem().toString();
			String speed = spinnerSpeed.getSelectedItem().toString();
			String partiy = spinnerParity.getSelectedItem().toString();

			String param = speed + ":" + partiy + ":8:1";

			com = COMReader.getCOMInstance(port);
			if (com == null) {
				showTip(getString(R.string.str_btn_com_open) + port
						+ getString(R.string.str_faild));
				return;
			}

			if (!com.open(param)) {
				// if (!com.open("9600:E:8:1")) {
				showTip(getString(R.string.str_configure) + port
						+ getString(R.string.str_faild));
				return;
			}

			btnOpen.setText(R.string.str_btn_com_close);
			spinnerPort.setEnabled(false);
			spinnerSpeed.setEnabled(false);
			spinnerParity.setEnabled(false);
			spinnerMode.setEnabled(false);

			
			opend = true;
		} else {
			if (com != null) {
				com.close();
				com = null;
			}

			btnOpen.setText(R.string.str_btn_com_open);
			spinnerPort.setEnabled(true);
			spinnerSpeed.setEnabled(true);
			spinnerParity.setEnabled(true);
			spinnerMode.setEnabled(true);

			opend = false;
		}
	}

	public void onClose(View v) {
		finish();
	}

	@Override
	protected void onPause() {
		// TODO Auto-generated method stub
//		if (com != null) {
//			com.close();
//		}

		super.onPause();
	}

	@Override
	protected void onResume() {
		// TODO Auto-generated method stub
		super.onResume();
	}
}
